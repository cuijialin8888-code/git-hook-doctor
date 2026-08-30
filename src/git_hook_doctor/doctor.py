from __future__ import annotations

import os
from pathlib import Path

from .config import KNOWN_HOOK_EVENT_SET, SERVER_HOOK_EVENTS, ParsedConfig, parse_config
from .git import GitInvocationError, discover_repository, read_relevant_config
from .hooks import analyze_configured_hook, analyze_traditional_hook, status_from_findings
from .models import Finding, HookResult, Report, RepositoryInfo, Severity


def validate_event_name(value: str) -> str:
    if not value or value in {".", ".."}:
        raise ValueError("Hook event name cannot be empty, '.' or '..'")
    if any(character in value for character in ("/", "\\", "\0", "\r", "\n")):
        raise ValueError(f"Hook event name must be a filename, not a path: {value!r}")
    return value


def _hook_directory_for_event(
    repository: RepositoryInfo,
    config: ParsedConfig,
    event: str,
) -> Path:
    if not config.core_hooks_path or event not in SERVER_HOOK_EVENTS or repository.is_bare:
        return repository.hooks_dir
    configured = Path(config.core_hooks_path.value).expanduser()
    if configured.is_absolute():
        return Path(os.path.abspath(configured))
    return Path(os.path.abspath(repository.git_dir / configured))


def _event_candidates(repository: RepositoryInfo, config: ParsedConfig) -> set[str]:
    events: set[str] = set()
    directories = {repository.hooks_dir}
    if config.core_hooks_path and not Path(config.core_hooks_path.value).expanduser().is_absolute():
        directories.add(Path(os.path.abspath(repository.git_dir / config.core_hooks_path.value)))
    for directory in directories:
        if not directory.is_dir():
            continue
        try:
            children = list(directory.iterdir())
        except OSError:
            children = []
        for child in children:
            name = child.name
            if name.endswith(".sample") or name.startswith("."):
                continue
            if name in KNOWN_HOOK_EVENT_SET:
                events.add(name)
                continue
            base = name.split(".", 1)[0]
            if base in KNOWN_HOOK_EVENT_SET:
                events.add(base)
    for hook in config.hooks.values():
        events.update(value for value, _entry in hook.events)
    return events


def _core_hooks_disabled(config: ParsedConfig, *, platform_name: str) -> bool:
    if not config.core_hooks_path:
        return False
    value = config.core_hooks_path.value.strip().strip('"\'').rstrip("/\\").lower()
    disabled = {"/dev/null"}
    if platform_name == "nt":
        disabled.update({"nul", "nul:"})
    return value in disabled


def _installed_traditional_path(
    directory: Path,
    event: str,
    *,
    platform_name: str,
) -> Path | None:
    exact = directory / event
    if exact.exists():
        return exact
    if platform_name == "nt":
        executable = directory / f"{event}.exe"
        if executable.exists():
            return executable
    return None


def _global_finding(
    code: str,
    severity: Severity,
    title: str,
    message: str,
    *,
    remediation: str = "",
    path: Path | None = None,
    hook: str | None = None,
    evidence: dict[str, object] | None = None,
) -> Finding:
    return Finding(
        code=code,
        severity=severity,
        title=title,
        message=message,
        remediation=remediation,
        path=path,
        line=1 if path else None,
        hook=hook,
        evidence=evidence or {},
    )


def _shadowed_hook_findings(
    repository: RepositoryInfo,
    config: ParsedConfig,
    events: set[str],
    *,
    platform_name: str,
) -> list[Finding]:
    findings: list[Finding] = []
    candidate_dirs: list[Path] = [repository.hooks_dir]
    if config.core_hooks_path and not Path(config.core_hooks_path.value).expanduser().is_absolute():
        candidate_dirs.append(Path(os.path.abspath(repository.git_dir / config.core_hooks_path.value)))
    default_dir = repository.common_dir / "hooks"
    candidate_dirs.append(default_dir)
    if not repository.is_bare:
        candidate_dirs.extend(
            repository.root / name for name in (".husky", ".githooks", ".git-hooks")
        )

    seen: set[Path] = set()
    for directory in candidate_dirs:
        directory = Path(os.path.abspath(directory))
        if directory in seen or not directory.is_dir():
            continue
        seen.add(directory)
        for event in sorted(events or KNOWN_HOOK_EVENT_SET):
            effective_directory = _hook_directory_for_event(repository, config, event)
            if directory == effective_directory:
                continue
            misplaced = _installed_traditional_path(
                directory, event, platform_name=platform_name
            )
            effective = _installed_traditional_path(
                effective_directory, event, platform_name=platform_name
            )
            if misplaced and misplaced.is_file() and effective is None:
                expected = effective_directory / event
                findings.append(
                    _global_finding(
                        "GHD013",
                        Severity.WARNING,
                        "Hook-like file is outside the effective hook directory",
                        f"Found {misplaced}, but Git resolves {event} to {expected}.",
                        remediation="Install the hook in Git's effective directory or correct core.hooksPath.",
                        path=misplaced,
                        hook=event,
                        evidence={
                            "effective_path": str(expected),
                            "core_hooks_path": config.core_hooks_path.value if config.core_hooks_path else None,
                        },
                    )
                )
    return findings


def _apply_event_switch(
    result: HookResult,
    repository: RepositoryInfo,
    config: ParsedConfig,
) -> None:
    settings = config.event_settings.get(result.event)
    if not settings or not settings.enabled or settings.is_enabled:
        return
    if repository.git_version >= (2, 55, 0):
        finding = _global_finding(
            "GHD017",
            Severity.INFO,
            "Hook event is disabled",
            f"hook.{result.event}.enabled is false, so Git skips every hook registered for this event.",
            remediation=f"Set hook.{result.event}.enabled=true only if this event is intended to run.",
            hook=result.event,
        )
        result.findings.append(finding)
        result.status = "disabled"
    else:
        finding = _global_finding(
            "GHD020",
            Severity.WARNING,
            "Event-level disable setting is unsupported",
            f"Git {repository.git_version_text} ignores hook.{result.event}.enabled; that switch requires Git 2.55 or newer.",
            remediation="Upgrade Git or disable configured hooks individually.",
            hook=result.event,
        )
        result.findings.append(finding)
        result.status = status_from_findings(result.findings)


def _disabled_event_result(event: str, path: Path | None = None) -> HookResult:
    finding = _global_finding(
        "GHD017",
        Severity.INFO,
        "Hook event is disabled",
        f"hook.{event}.enabled is false, so Git skips every hook registered for this event.",
        remediation=f"Set hook.{event}.enabled=true only if this event is intended to run.",
        path=path,
        hook=event,
    )
    return HookResult(
        event=event,
        source="event",
        label="event switch",
        status="disabled",
        path=path,
        findings=[finding],
    )


def diagnose(
    repo_path: Path,
    *,
    events: list[str] | None = None,
    git_executable: str = "git",
    platform_name: str | None = None,
) -> Report:
    requested = [validate_event_name(event) for event in (events or [])]
    repository = discover_repository(repo_path, git_executable=git_executable)
    entries = read_relevant_config(repository)
    config = parse_config(entries)
    explicit = bool(requested)
    candidates = set(requested) if explicit else _event_candidates(repository, config)

    hook_results: list[HookResult] = []
    findings: list[Finding] = []

    effective_platform = platform_name or os.name

    if _core_hooks_disabled(config, platform_name=effective_platform):
        findings.append(
            _global_finding(
                "GHD002",
                Severity.WARNING,
                "Traditional hooks are disabled",
                f"core.hooksPath points to {config.core_hooks_path.value!r}; Git will not find traditional hook files there.",
                remediation="Unset core.hooksPath or point it to a real directory if traditional hooks should run.",
                evidence=config.core_hooks_path.to_dict(),
            )
        )

    if (
        config.core_hooks_path
        and repository.is_linked_worktree
        and not Path(config.core_hooks_path.value).expanduser().is_absolute()
        and not repository.hooks_dir.exists()
    ):
        findings.append(
            _global_finding(
                "GHD021",
                Severity.WARNING,
                "Relative hooksPath resolves to a missing worktree path",
                f"This linked worktree resolves core.hooksPath={config.core_hooks_path.value!r} to {repository.hooks_dir}, which does not exist.",
                remediation="Use git rev-parse --git-path hooks when installing hooks, or choose an absolute/shared path deliberately.",
                path=repository.hooks_dir,
                evidence={"config_origin": config.core_hooks_path.origin},
            )
        )

    if config.global_jobs and repository.git_version < (2, 55, 0):
        findings.append(
            _global_finding(
                "GHD020",
                Severity.WARNING,
                "Global hook parallelism setting is unsupported",
                f"Git {repository.git_version_text} ignores hook.jobs; configured-hook parallelism requires Git 2.55 or newer.",
                remediation="Upgrade Git or expect serial hook execution.",
                evidence=config.global_jobs.to_dict(),
            )
        )
    for event, settings in config.event_settings.items():
        if settings.jobs and repository.git_version < (2, 55, 0):
            findings.append(
                _global_finding(
                    "GHD020",
                    Severity.WARNING,
                    "Per-event hook parallelism setting is unsupported",
                    f"Git {repository.git_version_text} ignores hook.{event}.jobs; this setting requires Git 2.55 or newer.",
                    remediation="Upgrade Git or expect serial hook execution.",
                    hook=event,
                    evidence=settings.jobs.to_dict(),
                )
            )

    for event in sorted(candidates):
        configured_results: list[HookResult] = []
        for configured in config.hooks.values():
            if any(value == event for value, _entry in configured.events):
                result = analyze_configured_hook(
                    configured,
                    event,
                    repository,
                    config.event_settings.get(event),
                    platform_name=platform_name,
                )
                configured_results.append(result)
                hook_results.append(result)
                findings.extend(result.findings)

        traditional_path = _hook_directory_for_event(repository, config, event) / event
        windows_executable = traditional_path.with_name(f"{event}.exe")
        installed_traditional = _installed_traditional_path(
            traditional_path.parent,
            event,
            platform_name=effective_platform,
        )
        variants_exist = any(
            candidate.exists()
            for candidate in (
                traditional_path.with_name(f"{event}.sample"),
                traditional_path.with_name(f"{event}.sh"),
                traditional_path.with_name(f"{event}.py"),
                windows_executable,
            )
        )
        settings = config.event_settings.get(event)
        event_disabled = bool(
            settings
            and settings.enabled
            and not settings.is_enabled
            and repository.git_version >= (2, 55, 0)
        )
        configured_runnable = any(
            result.status in {"ready", "warning"} for result in configured_results
        )

        if event_disabled:
            if installed_traditional or (explicit and not configured_results):
                result = _disabled_event_result(
                    event, installed_traditional
                )
                hook_results.append(result)
                findings.extend(result.findings)
        elif (
            installed_traditional is not None
            or ((variants_exist or explicit) and not configured_runnable)
        ):
            result = analyze_traditional_hook(
                event,
                traditional_path,
                repository,
                explicit=explicit,
                platform_name=platform_name,
            )
            _apply_event_switch(result, repository, config)
            hook_results.append(result)
            findings.extend(result.findings)

    shadowed = _shadowed_hook_findings(
        repository,
        config,
        candidates,
        platform_name=effective_platform,
    )
    findings.extend(shadowed)

    if not hook_results and not candidates:
        findings.append(
            _global_finding(
                "GHD001",
                Severity.INFO,
                "No hooks discovered",
                "No traditional hooks or configured hook events were found in this repository.",
                remediation="Run 'git-hook-doctor explain pre-commit' to diagnose a hook you expected to exist.",
            )
        )

    return Report(
        repository=repository,
        core_hooks_path=config.core_hooks_path,
        hooks=hook_results,
        findings=findings,
        requested_events=requested,
    )


__all__ = ["GitInvocationError", "diagnose", "validate_event_name"]

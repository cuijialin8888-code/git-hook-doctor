from __future__ import annotations

import os
import re
import shlex
import shutil
import stat
from pathlib import Path

from .config import (
    ConfiguredHook,
    EventSettings,
    KNOWN_HOOK_EVENT_SET,
    SERVER_HOOK_EVENTS,
)
from .models import Finding, HookResult, RepositoryInfo, Severity


_BINARY_MAGIC = (
    b"\x7fELF",
    b"MZ",
    b"\xfe\xed\xfa\xce",
    b"\xfe\xed\xfa\xcf",
    b"\xce\xfa\xed\xfe",
    b"\xcf\xfa\xed\xfe",
)

_HOOK_INSPECTION_BYTES = 8192

_SHELL_BUILTINS = {
    ".",
    ":",
    "break",
    "cd",
    "continue",
    "echo",
    "eval",
    "exec",
    "exit",
    "export",
    "false",
    "printf",
    "pwd",
    "read",
    "set",
    "shift",
    "test",
    "times",
    "trap",
    "true",
    "type",
    "ulimit",
    "umask",
    "unset",
    "wait",
}


def _finding(
    code: str,
    severity: Severity,
    title: str,
    message: str,
    *,
    hook: str,
    path: Path | None = None,
    remediation: str = "",
    evidence: dict[str, object] | None = None,
) -> Finding:
    return Finding(
        code=code,
        severity=severity,
        title=title,
        message=message,
        hook=hook,
        path=path,
        line=1 if path else None,
        remediation=remediation,
        evidence=evidence or {},
    )


def status_from_findings(findings: list[Finding], *, disabled: bool = False) -> str:
    if disabled:
        return "disabled"
    if any(finding.severity is Severity.ERROR for finding in findings):
        return "blocked"
    if any(finding.severity is Severity.WARNING for finding in findings):
        return "warning"
    return "ready"


def _git_for_windows_root(repository: RepositoryInfo) -> Path | None:
    resolved = shutil.which(repository.git_executable)
    if not resolved:
        return None
    git_path = Path(resolved).resolve()
    parent = git_path.parent
    if parent.name.lower() in {"cmd", "bin", "mingw64", "mingw32"}:
        return parent.parent
    return None


def _resolve_program(name: str, repository: RepositoryInfo, *, platform_name: str) -> Path | None:
    candidate = Path(name).expanduser()
    if platform_name != "nt":
        if candidate.is_absolute():
            return candidate if candidate.exists() else None
        resolved = shutil.which(name)
        return Path(resolved) if resolved else None

    if name.startswith(("/bin/", "/usr/bin/")):
        root = _git_for_windows_root(repository)
        if root:
            basename = Path(name).name
            for directory in (root / "usr" / "bin", root / "bin"):
                for suffix in (".exe", ""):
                    path = directory / f"{basename}{suffix}"
                    if path.exists():
                        return path
        return None

    if candidate.is_absolute():
        return candidate if candidate.exists() else None
    resolved = shutil.which(name)
    if resolved:
        return Path(resolved)
    root = _git_for_windows_root(repository)
    if root:
        for directory in (root / "usr" / "bin", root / "bin"):
            for suffix in (".exe", ""):
                path = directory / f"{name}{suffix}"
                if path.exists():
                    return path
    return None


def _shebang_program(spec: str) -> tuple[str | None, str | None]:
    try:
        tokens = shlex.split(spec, posix=True)
    except ValueError:
        return None, None
    if not tokens:
        return None, None
    interpreter = tokens[0]
    if Path(interpreter).name != "env":
        return interpreter, None

    index = 1
    while index < len(tokens):
        token = tokens[index]
        if token == "-S":
            index += 1
            break
        if token.startswith("-") or ("=" in token and not token.startswith("=")):
            index += 1
            continue
        break
    target = tokens[index] if index < len(tokens) else None
    return interpreter, target


def _looks_binary(data: bytes) -> bool:
    return b"\0" in data or any(data.startswith(magic) for magic in _BINARY_MAGIC)


def analyze_traditional_hook(
    event: str,
    path: Path,
    repository: RepositoryInfo,
    *,
    explicit: bool,
    platform_name: str | None = None,
) -> HookResult:
    platform_name = platform_name or os.name
    findings: list[Finding] = []

    if platform_name == "nt" and not path.exists():
        windows_executable = path.with_name(f"{event}.exe")
        if windows_executable.exists():
            path = windows_executable

    if path.is_symlink() and not path.exists():
        findings.append(
            _finding(
                "GHD006",
                Severity.ERROR,
                "Broken hook symlink",
                f"Git resolves {event} to a symlink whose target does not exist.",
                hook=event,
                path=path,
                remediation="Repair the symlink target or replace the hook with a valid executable.",
            )
        )
        return HookResult(event, "traditional", event, "blocked", path=path, findings=findings)

    if not path.exists():
        if explicit:
            findings.append(
                _finding(
                    "GHD003",
                    Severity.ERROR,
                    "Hook file is missing",
                    f"Git will look for {event} at {path}, but that file does not exist.",
                    hook=event,
                    path=path,
                    remediation="Install the hook at Git's effective hook path or correct core.hooksPath.",
                )
            )
            sample = path.with_name(f"{event}.sample")
            if sample.exists():
                findings.append(
                    _finding(
                        "GHD004",
                        Severity.WARNING,
                        "Only the sample hook exists",
                        f"{sample.name} is a template; Git does not run files ending in .sample.",
                        hook=event,
                        path=sample,
                        remediation=f"Copy or rename the intended implementation to {event}, then make it executable.",
                    )
                )
            if path.parent.exists():
                ignored_names = {f"{event}.sample"}
                if platform_name == "nt":
                    ignored_names.add(f"{event}.exe")
                variants = sorted(
                    candidate
                    for candidate in path.parent.glob(f"{event}.*")
                    if candidate.name not in ignored_names
                )
                if variants:
                    findings.append(
                        _finding(
                            "GHD005",
                            Severity.ERROR,
                            "Hook has a filename extension",
                            f"Git looks for the exact name {event}; found {', '.join(item.name for item in variants)} instead.",
                            hook=event,
                            path=variants[0],
                            remediation=f"Use the exact filename {event} without .sh, .py, or another extension.",
                        )
                    )
        return HookResult(
            event,
            "traditional",
            event,
            status_from_findings(findings),
            path=path,
            findings=findings,
        )

    if not path.is_file():
        findings.append(
            _finding(
                "GHD006",
                Severity.ERROR,
                "Hook path is not a regular file",
                f"Git resolves {event} to {path}, which is not a regular file.",
                hook=event,
                path=path,
                remediation="Replace it with an executable file or a valid symlink to one.",
            )
        )
        return HookResult(event, "traditional", event, "blocked", path=path, findings=findings)

    if platform_name != "nt" and not (path.stat().st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)):
        findings.append(
            _finding(
                "GHD007",
                Severity.ERROR,
                "Hook is not executable",
                "Git ignores traditional hook files without an executable bit.",
                hook=event,
                path=path,
                remediation=f"Run chmod +x {shlex.quote(str(path))} and commit the executable mode when the hook is tracked.",
            )
        )

    try:
        with path.open("rb") as stream:
            data = stream.read(_HOOK_INSPECTION_BYTES)
    except OSError as exc:
        findings.append(
            _finding(
                "GHD022",
                Severity.ERROR,
                "Hook cannot be read",
                f"Reading the hook failed: {exc}",
                hook=event,
                path=path,
                remediation="Fix the file permissions and verify the hook can be read by the current user.",
            )
        )
        return HookResult(event, "traditional", event, "blocked", path=path, findings=findings)

    if not data:
        findings.append(
            _finding(
                "GHD008",
                Severity.ERROR,
                "Hook is empty",
                "The hook file exists but contains no program to run.",
                hook=event,
                path=path,
                remediation="Add a valid script or remove the empty hook if it is not intended to run.",
            )
        )
    elif not _looks_binary(data):
        if data.startswith(b"\xef\xbb\xbf"):
            findings.append(
                _finding(
                    "GHD011",
                    Severity.ERROR,
                    "UTF-8 BOM appears before the shebang",
                    "The byte-order mark prevents the operating system from recognizing #! at byte zero.",
                    hook=event,
                    path=path,
                    remediation="Save the hook as UTF-8 without BOM.",
                )
            )
            shebang_data = data[3:]
        else:
            shebang_data = data

        first_line = shebang_data.split(b"\n", 1)[0]
        if not shebang_data.startswith(b"#!"):
            findings.append(
                _finding(
                    "GHD009",
                    Severity.ERROR,
                    "Text hook has no shebang",
                    "Git executes the hook as a program; a text script needs an interpreter line such as #!/usr/bin/env sh.",
                    hook=event,
                    path=path,
                    remediation="Add a valid shebang on the first byte of the file.",
                )
            )
        else:
            if first_line.endswith(b"\r"):
                findings.append(
                    _finding(
                        "GHD010",
                        Severity.ERROR,
                        "Shebang uses CRLF line endings",
                        "The carriage return becomes part of the interpreter name or argument and commonly makes the hook fail to start.",
                        hook=event,
                        path=path,
                        remediation="Store hook scripts with LF line endings, for example via .gitattributes.",
                    )
                )
            spec = first_line[2:].rstrip(b"\r").decode("utf-8", "replace").strip()
            interpreter, env_target = _shebang_program(spec)
            if not interpreter:
                findings.append(
                    _finding(
                        "GHD012",
                        Severity.ERROR,
                        "Shebang cannot be parsed",
                        f"The interpreter declaration is not valid: {spec!r}.",
                        hook=event,
                        path=path,
                        remediation="Use a simple absolute interpreter path or /usr/bin/env followed by a program name.",
                    )
                )
            else:
                is_env = Path(interpreter).name == "env"
                missing_target = is_env and not env_target
                target = env_target if is_env else interpreter
                if missing_target:
                    findings.append(
                        _finding(
                            "GHD012",
                            Severity.ERROR,
                            "env shebang has no target program",
                            "/usr/bin/env needs a program name after its options.",
                            hook=event,
                            path=path,
                            remediation="Use a shebang such as #!/usr/bin/env sh or #!/usr/bin/env python3.",
                        )
                    )
                elif _resolve_program(interpreter, repository, platform_name=platform_name) is None:
                    findings.append(
                        _finding(
                            "GHD012",
                            Severity.ERROR,
                            "Hook interpreter is unavailable",
                            f"The shebang selects {interpreter!r}, but Git Hook Doctor could not resolve it in the current environment.",
                            hook=event,
                            path=path,
                            remediation="Install the interpreter or change the shebang to one available where Git runs.",
                            evidence={"interpreter": interpreter},
                        )
                    )
                elif target and _resolve_program(target, repository, platform_name=platform_name) is None:
                    findings.append(
                        _finding(
                            "GHD012",
                            Severity.ERROR,
                            "Hook interpreter is unavailable",
                            f"The shebang selects {target!r}, but Git Hook Doctor could not resolve it in the current environment.",
                            hook=event,
                            path=path,
                            remediation="Install the interpreter or change the shebang to one available where Git runs.",
                            evidence={"interpreter": target},
                        )
                    )

    return HookResult(
        event=event,
        source="traditional",
        label=event,
        status=status_from_findings(findings),
        path=path,
        findings=findings,
    )


def _plain_command_tokens(command: str, *, platform_name: str) -> list[str] | None:
    if any(character in command for character in "|&;<>()$`\n"):
        return None
    try:
        tokens = shlex.split(command, posix=platform_name != "nt")
    except ValueError:
        return None
    return [token.strip('"\'') for token in tokens]


def _plain_command_target(command: str, *, platform_name: str) -> str | None:
    tokens = _plain_command_tokens(command, platform_name=platform_name)
    if tokens is None:
        return None
    index = 0
    assignment = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
    while index < len(tokens) and assignment.match(tokens[index]):
        index += 1
    if index < len(tokens) and Path(tokens[index]).name == "env":
        index += 1
        while index < len(tokens) and (
            tokens[index].startswith("-") or assignment.match(tokens[index])
        ):
            index += 1
    if index >= len(tokens):
        return ""
    return tokens[index]


def _command_preview(command: str, *, platform_name: str) -> str:
    target = _plain_command_target(command, platform_name=platform_name)
    if target is None:
        return "<shell command omitted>"
    if target == "":
        return ""
    tokens = _plain_command_tokens(command, platform_name=platform_name) or []
    return target if tokens == [target] else f"{target} ..."


def _resolve_configured_target(
    target: str,
    repository: RepositoryInfo,
    *,
    event: str,
    platform_name: str,
) -> Path | None:
    expanded = Path(target).expanduser()
    if expanded.is_absolute() or target.startswith((".", "~")) or "/" in target or "\\" in target:
        if not expanded.is_absolute():
            working_directory = (
                repository.git_dir
                if repository.is_bare or event in SERVER_HOOK_EVENTS
                else repository.root
            )
            expanded = working_directory / expanded
        return expanded if expanded.exists() else None
    return _resolve_program(target, repository, platform_name=platform_name)


def analyze_configured_hook(
    hook: ConfiguredHook,
    event: str,
    repository: RepositoryInfo,
    settings: EventSettings | None,
    *,
    platform_name: str | None = None,
) -> HookResult:
    platform_name = platform_name or os.name
    findings: list[Finding] = []
    disabled = False
    version = repository.git_version
    raw_command = hook.command.value if hook.command else None
    command = (
        _command_preview(raw_command, platform_name=platform_name)
        if raw_command is not None
        else None
    )
    entry = next((item for value, item in hook.events if value == event), None)
    origin = (entry or hook.command or hook.enabled)

    if version < (2, 54, 0):
        findings.append(
            _finding(
                "GHD014",
                Severity.ERROR,
                "Configured hooks are unsupported by this Git version",
                f"Git {repository.git_version_text} ignores hook.<name>.event/command; configured hooks require Git 2.54 or newer.",
                hook=event,
                remediation="Upgrade Git to 2.54+ or install an equivalent traditional hook in the effective hook directory.",
                evidence={"friendly_name": hook.name, "minimum_git": "2.54.0"},
            )
        )
    elif not hook.is_enabled:
        disabled = True
        findings.append(
            _finding(
                "GHD016",
                Severity.INFO,
                "Configured hook is disabled",
                f"hook.{hook.name}.enabled is false, so Git will skip this configured hook.",
                hook=event,
                remediation=f"Set hook.{hook.name}.enabled=true only if this hook is intended to run.",
            )
        )

    if settings and settings.enabled and not settings.is_enabled:
        if version >= (2, 55, 0):
            disabled = True
            findings.append(
                _finding(
                    "GHD017",
                    Severity.INFO,
                    "Hook event is disabled",
                    f"hook.{event}.enabled is false, so Git skips every hook registered for this event.",
                    hook=event,
                    remediation=f"Set hook.{event}.enabled=true only if this event is intended to run.",
                )
            )
        else:
            findings.append(
                _finding(
                    "GHD020",
                    Severity.WARNING,
                    "Event-level disable setting is unsupported",
                    f"Git {repository.git_version_text} does not honor hook.{event}.enabled; that switch requires Git 2.55 or newer.",
                    hook=event,
                    remediation="Upgrade Git or disable each configured hook individually.",
                )
            )

    if hook.name in KNOWN_HOOK_EVENT_SET:
        findings.append(
            _finding(
                "GHD019",
                Severity.ERROR,
                "Configured hook name collides with an event",
                f"{hook.name!r} is both a friendly name and a known event name; current Git rejects this ambiguity.",
                hook=event,
                remediation="Choose a distinct friendly name, for example company-linter or no-secrets.",
            )
        )

    if not disabled:
        if not hook.command or not hook.command.value.strip():
            findings.append(
                _finding(
                    "GHD015",
                    Severity.ERROR,
                    "Configured hook has no command",
                    f"hook.{hook.name}.event includes {event}, but hook.{hook.name}.command is missing or empty.",
                    hook=event,
                    remediation=f"Set hook.{hook.name}.command to the intended executable or shell command.",
                )
            )
        else:
            target = _plain_command_target(hook.command.value, platform_name=platform_name)
            if target == "":
                findings.append(
                    _finding(
                        "GHD015",
                        Severity.ERROR,
                        "Configured hook command is empty",
                        f"hook.{hook.name}.command does not contain a runnable command.",
                        hook=event,
                        remediation=f"Set hook.{hook.name}.command to the intended executable or shell command.",
                    )
                )
            elif target and target not in _SHELL_BUILTINS:
                resolved = _resolve_configured_target(
                    target,
                    repository,
                    event=event,
                    platform_name=platform_name,
                )
                if resolved is None:
                    findings.append(
                        _finding(
                            "GHD018",
                            Severity.ERROR,
                            "Configured hook command cannot be resolved",
                            f"The command starts with {target!r}, which is neither an existing path nor an executable on PATH.",
                            hook=event,
                            remediation="Install the command or correct hook.<name>.command at the reported config origin.",
                            evidence={"friendly_name": hook.name, "target": target},
                        )
                    )

    if hook.parallel and version < (2, 55, 0):
        findings.append(
            _finding(
                "GHD020",
                Severity.WARNING,
                "Parallel hook setting is unsupported",
                f"Git {repository.git_version_text} ignores hook.{hook.name}.parallel; configured-hook parallelism requires Git 2.55 or newer.",
                hook=event,
                remediation="Upgrade Git or expect serial execution.",
            )
        )

    return HookResult(
        event=event,
        source="configured",
        label=hook.name,
        status=status_from_findings(findings, disabled=disabled),
        command=command,
        scope=origin.scope if origin else None,
        origin=origin.origin if origin else None,
        findings=findings,
    )

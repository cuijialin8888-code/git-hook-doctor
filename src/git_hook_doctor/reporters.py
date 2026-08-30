from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import __version__
from .models import Finding, Report, Severity


_COLORS = {
    "red": "\x1b[31m",
    "yellow": "\x1b[33m",
    "green": "\x1b[32m",
    "blue": "\x1b[34m",
    "bold": "\x1b[1m",
    "reset": "\x1b[0m",
}


def _paint(text: str, color: str, enabled: bool) -> str:
    if not enabled:
        return text
    return f"{_COLORS[color]}{text}{_COLORS['reset']}"


def _display_path(path: Path | None, root: Path) -> str:
    if path is None:
        return ""
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def text_report(report: Report, *, color: bool = False) -> str:
    repository = report.repository
    lines = [
        _paint(f"Git Hook Doctor {__version__}", "bold", color),
        f"Repository: {repository.root}",
        f"Git: {repository.git_version_text}",
        f"Hook directory: {repository.hooks_dir}",
    ]
    if report.core_hooks_path:
        lines.append(
            "core.hooksPath: "
            f"{report.core_hooks_path.value} "
            f"({report.core_hooks_path.scope}, {report.core_hooks_path.origin})"
        )
    if repository.is_linked_worktree:
        lines.append(f"Worktree: linked ({repository.git_dir})")
    lines.extend(["Safety: read-only; no hooks executed", ""])

    status_colors = {"ready": "green", "warning": "yellow", "blocked": "red", "disabled": "blue"}
    for hook in report.hooks:
        heading = f"[{hook.status.upper()}] {hook.event} ({hook.source}: {hook.label})"
        lines.append(_paint(heading, status_colors[hook.status], color))
        if hook.path:
            lines.append(f"  Path: {_display_path(hook.path, repository.root)}")
        if hook.command:
            lines.append(f"  Command: {hook.command}")
        if hook.scope or hook.origin:
            lines.append(f"  Config: {hook.scope or 'unknown'} / {hook.origin or 'unknown'}")
        for finding in hook.findings:
            severity_color = {
                Severity.ERROR: "red",
                Severity.WARNING: "yellow",
                Severity.INFO: "blue",
            }[finding.severity]
            prefix = f"  {finding.severity.value.upper()} {finding.code} {finding.title}"
            lines.append(_paint(prefix, severity_color, color))
            lines.append(f"    {finding.message}")
            if finding.remediation:
                lines.append(f"    Fix: {finding.remediation}")
        lines.append("")

    hook_findings = {id(finding) for hook in report.hooks for finding in hook.findings}
    global_findings = [finding for finding in report.findings if id(finding) not in hook_findings]
    if global_findings:
        lines.append(_paint("Repository findings", "bold", color))
        for finding in global_findings:
            severity_color = {
                Severity.ERROR: "red",
                Severity.WARNING: "yellow",
                Severity.INFO: "blue",
            }[finding.severity]
            lines.append(
                _paint(
                    f"  {finding.severity.value.upper()} {finding.code} {finding.title}",
                    severity_color,
                    color,
                )
            )
            lines.append(f"    {finding.message}")
            if finding.path:
                lines.append(f"    Path: {_display_path(finding.path, repository.root)}")
            if finding.remediation:
                lines.append(f"    Fix: {finding.remediation}")
        lines.append("")

    counts = report.counts
    lines.append(
        "Summary: "
        f"{counts['ready']} ready, {counts['warning_hooks']} warning, "
        f"{counts['blocked']} blocked, {counts['disabled']} disabled; "
        f"{counts['error']} errors, {counts['warning']} warnings, {counts['info']} info"
    )
    return "\n".join(lines).rstrip() + "\n"


def json_report(report: Report) -> str:
    return json.dumps(report.to_dict(), indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def markdown_report(report: Report) -> str:
    repo = report.repository
    lines = [
        "# Git Hook Doctor report",
        "",
        f"- Repository: `{repo.root}`",
        f"- Git: `{repo.git_version_text}`",
        f"- Hook directory: `{repo.hooks_dir}`",
        "- Safety: read-only; no hooks executed",
        "",
        "| Event | Source | Hook | Status | Path or command |",
        "|---|---|---|---|---|",
    ]
    for hook in report.hooks:
        target = _display_path(hook.path, repo.root) if hook.path else (hook.command or "")
        target = target.replace("|", "\\|")
        lines.append(
            f"| `{hook.event}` | {hook.source} | `{hook.label}` | **{hook.status}** | `{target}` |"
        )
    if not report.hooks:
        lines.append("| — | — | — | no hooks discovered | — |")

    lines.extend(["", "## Findings", ""])
    if not report.findings:
        lines.append("No findings.")
    else:
        for finding in report.findings:
            lines.append(f"### {finding.severity.value.upper()} {finding.code}: {finding.title}")
            lines.append("")
            lines.append(finding.message)
            if finding.path:
                lines.extend(["", f"Path: `{_display_path(finding.path, repo.root)}`"])
            if finding.remediation:
                lines.extend(["", f"Suggested fix: {finding.remediation}"])
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _sarif_location(finding: Finding, root: Path) -> list[dict[str, Any]]:
    if finding.path is None:
        return []
    uri = _display_path(finding.path, root).replace("\\", "/")
    location: dict[str, Any] = {"artifactLocation": {"uri": uri}}
    if finding.line:
        location["region"] = {"startLine": finding.line}
    return [{"physicalLocation": location}]


def sarif_report(report: Report) -> str:
    unique_rules: dict[str, Finding] = {}
    for finding in report.findings:
        unique_rules.setdefault(finding.code, finding)
    level = {Severity.ERROR: "error", Severity.WARNING: "warning", Severity.INFO: "note"}
    document = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "Git Hook Doctor",
                        "version": __version__,
                        "informationUri": "https://github.com/cuijialin8888-code/git-hook-doctor",
                        "rules": [
                            {
                                "id": code,
                                "name": finding.title,
                                "shortDescription": {"text": finding.title},
                                "helpUri": (
                                    "https://github.com/cuijialin8888-code/git-hook-doctor/"
                                    f"blob/main/docs/rules.md#{code.lower()}"
                                ),
                                "defaultConfiguration": {"level": level[finding.severity]},
                            }
                            for code, finding in sorted(unique_rules.items())
                        ],
                    }
                },
                "invocations": [
                    {
                        "executionSuccessful": True,
                        "properties": {"readOnly": True, "hooksExecuted": False},
                    }
                ],
                "results": [
                    {
                        "ruleId": finding.code,
                        "level": level[finding.severity],
                        "message": {"text": f"{finding.title}: {finding.message}"},
                        "locations": _sarif_location(finding, report.repository.root),
                        "properties": {
                            "hook": finding.hook,
                            "remediation": finding.remediation,
                            "evidence": finding.evidence,
                        },
                    }
                    for finding in report.findings
                ],
            }
        ],
    }
    return json.dumps(document, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def render(report: Report, format_name: str, *, color: bool = False) -> str:
    if format_name == "text":
        return text_report(report, color=color)
    if format_name == "json":
        return json_report(report)
    if format_name == "markdown":
        return markdown_report(report)
    if format_name == "sarif":
        return sarif_report(report)
    raise ValueError(f"Unsupported report format: {format_name}")

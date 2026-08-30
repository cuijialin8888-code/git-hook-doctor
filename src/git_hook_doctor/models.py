from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"

    @property
    def rank(self) -> int:
        return {Severity.INFO: 0, Severity.WARNING: 1, Severity.ERROR: 2}[self]

    @classmethod
    def parse(cls, value: str) -> "Severity":
        return cls(value.lower())


@dataclass(frozen=True)
class ConfigEntry:
    scope: str
    origin: str
    key: str
    value: str

    def to_dict(self) -> dict[str, str]:
        return {
            "scope": self.scope,
            "origin": self.origin,
            "key": self.key,
            "value": self.value,
        }


@dataclass(frozen=True)
class Finding:
    code: str
    severity: Severity
    title: str
    message: str
    remediation: str = ""
    path: Path | None = None
    line: int | None = None
    hook: str | None = None
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self, root: Path | None = None) -> dict[str, Any]:
        path_value: str | None = None
        if self.path is not None:
            try:
                path_value = str(self.path.relative_to(root)) if root else str(self.path)
            except ValueError:
                path_value = str(self.path)
        result: dict[str, Any] = {
            "code": self.code,
            "severity": self.severity.value,
            "title": self.title,
            "message": self.message,
            "remediation": self.remediation,
            "path": path_value,
            "line": self.line,
            "hook": self.hook,
            "evidence": self.evidence,
        }
        return result


@dataclass
class HookResult:
    event: str
    source: str
    label: str
    status: str
    path: Path | None = None
    command: str | None = None
    scope: str | None = None
    origin: str | None = None
    findings: list[Finding] = field(default_factory=list)

    def to_dict(self, root: Path) -> dict[str, Any]:
        path_value: str | None = None
        if self.path is not None:
            try:
                path_value = str(self.path.relative_to(root))
            except ValueError:
                path_value = str(self.path)
        return {
            "event": self.event,
            "source": self.source,
            "label": self.label,
            "status": self.status,
            "path": path_value,
            "command": self.command,
            "scope": self.scope,
            "origin": self.origin,
            "finding_codes": [finding.code for finding in self.findings],
        }


@dataclass(frozen=True)
class RepositoryInfo:
    root: Path
    git_dir: Path
    common_dir: Path
    hooks_dir: Path
    hook_working_dir: Path
    git_executable: str
    git_version: tuple[int, int, int]
    git_version_text: str
    is_bare: bool
    is_linked_worktree: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": str(self.root),
            "git_dir": str(self.git_dir),
            "common_dir": str(self.common_dir),
            "hooks_dir": str(self.hooks_dir),
            "hook_working_dir": str(self.hook_working_dir),
            "git_executable": self.git_executable,
            "git_version": self.git_version_text,
            "is_bare": self.is_bare,
            "is_linked_worktree": self.is_linked_worktree,
        }


@dataclass
class Report:
    repository: RepositoryInfo
    core_hooks_path: ConfigEntry | None
    hooks: list[HookResult]
    findings: list[Finding]
    requested_events: list[str]
    schema_version: str = "1"

    @property
    def counts(self) -> dict[str, int]:
        counts = {severity.value: 0 for severity in Severity}
        for finding in self.findings:
            counts[finding.severity.value] += 1
        counts.update(
            {
                "ready": sum(hook.status == "ready" for hook in self.hooks),
                "blocked": sum(hook.status == "blocked" for hook in self.hooks),
                "warning_hooks": sum(hook.status == "warning" for hook in self.hooks),
                "disabled": sum(hook.status == "disabled" for hook in self.hooks),
            }
        )
        return counts

    def should_fail(self, threshold: Severity | None) -> bool:
        if threshold is None:
            return False
        return any(finding.severity.rank >= threshold.rank for finding in self.findings)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "safety": {"read_only": True, "hooks_executed": False},
            "repository": self.repository.to_dict(),
            "core_hooks_path": self.core_hooks_path.to_dict() if self.core_hooks_path else None,
            "requested_events": self.requested_events,
            "summary": self.counts,
            "hooks": [hook.to_dict(self.repository.root) for hook in self.hooks],
            "findings": [finding.to_dict(self.repository.root) for finding in self.findings],
        }

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from git_hook_doctor.models import Finding, HookResult, Report, RepositoryInfo, Severity
from git_hook_doctor.reporters import (
    github_report,
    json_report,
    markdown_report,
    sarif_report,
    text_report,
)


class ReporterTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory(prefix="git-hook-doctor-report-")
        root = Path(self._temporary.name)
        repository = RepositoryInfo(
            root=root,
            git_dir=root / ".git",
            common_dir=root / ".git",
            hooks_dir=root / ".git" / "hooks",
            hook_working_dir=root,
            git_executable="git",
            git_version=(2, 55, 0),
            git_version_text="2.55.0",
            is_bare=False,
            is_linked_worktree=False,
        )
        finding = Finding(
            code="GHD010",
            severity=Severity.ERROR,
            title="Shebang uses CRLF line endings",
            message="The hook cannot start.",
            remediation="Use LF.",
            path=repository.hooks_dir / "pre-commit",
            line=1,
            hook="pre-commit",
        )
        hook = HookResult(
            event="pre-commit",
            source="traditional",
            label="pre-commit",
            status="blocked",
            path=finding.path,
            findings=[finding],
        )
        self.report = Report(repository, None, [hook], [finding], ["pre-commit"])

    def tearDown(self) -> None:
        self._temporary.cleanup()

    def test_json_is_structured_and_marks_no_execution(self) -> None:
        payload = json.loads(json_report(self.report))
        self.assertFalse(payload["safety"]["hooks_executed"])
        self.assertEqual("GHD010", payload["findings"][0]["code"])

    def test_sarif_has_rule_and_location(self) -> None:
        payload = json.loads(sarif_report(self.report))
        run = payload["runs"][0]
        self.assertEqual("GHD010", run["results"][0]["ruleId"])
        self.assertEqual(".git/hooks/pre-commit", run["results"][0]["locations"][0]["physicalLocation"]["artifactLocation"]["uri"])

    def test_text_and_markdown_include_safety_boundary(self) -> None:
        self.assertIn("no hooks executed", text_report(self.report))
        self.assertIn("no hooks executed", markdown_report(self.report))

    def test_github_report_emits_escaped_native_annotation(self) -> None:
        output = github_report(self.report)
        self.assertIn(
            "::error file=.git/hooks/pre-commit,line=1,title=GHD010::",
            output,
        )
        self.assertIn("read-only, no hooks executed", output)


if __name__ == "__main__":
    raise SystemExit(unittest.main())

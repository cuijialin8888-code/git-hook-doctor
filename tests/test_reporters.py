from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from urllib.parse import urlsplit

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

    def test_sarif_encodes_reserved_characters_in_relative_paths(self) -> None:
        path = self.report.repository.root / "hooks #?%" / "pre-commit"
        self.report.findings = [replace(self.report.findings[0], path=path)]
        payload = json.loads(sarif_report(self.report))
        location = payload["runs"][0]["results"][0]["locations"][0]["physicalLocation"]
        uri = location["artifactLocation"]["uri"]
        self.assertEqual("hooks%20%23%3F%25/pre-commit", uri)
        self.assertEqual("", urlsplit(uri).query)
        self.assertEqual("", urlsplit(uri).fragment)
        self.assertEqual(1, location["region"]["startLine"])

    def test_sarif_encodes_unicode_without_changing_json_paths(self) -> None:
        path = self.report.repository.root / "钩子" / "pre-commit"
        self.report.findings = [replace(self.report.findings[0], path=path)]
        payload = json.loads(sarif_report(self.report))
        uri = payload["runs"][0]["results"][0]["locations"][0]["physicalLocation"]["artifactLocation"]["uri"]
        self.assertEqual("%E9%92%A9%E5%AD%90/pre-commit", uri)
        self.assertEqual(str(Path("钩子") / "pre-commit"), json.loads(json_report(self.report))["findings"][0]["path"])

    def test_sarif_uses_file_uri_for_external_hooks(self) -> None:
        path = self.report.repository.root.parent / "external hooks #" / "pre-commit"
        self.report.findings = [replace(self.report.findings[0], path=path)]
        payload = json.loads(sarif_report(self.report))
        uri = payload["runs"][0]["results"][0]["locations"][0]["physicalLocation"]["artifactLocation"]["uri"]
        parsed = urlsplit(uri)
        self.assertEqual("file", parsed.scheme)
        self.assertTrue(parsed.path.endswith("/external%20hooks%20%23/pre-commit"))
        self.assertEqual("", parsed.fragment)

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

from __future__ import annotations

import json
import io
import os
from pathlib import Path
from contextlib import redirect_stderr, redirect_stdout

from git_hook_doctor.cli import main

from support import GitRepositoryTestCase


class CliTests(GitRepositoryTestCase):
    def test_sarif_locates_hook_in_custom_directory_with_special_characters(self) -> None:
        custom = self.repo / "hooks space % #"
        self.write_hook("pre-commit", b"#!/bin/sh\r\nexit 0\r\n", directory=custom)
        self.git("config", "core.hooksPath", str(custom))
        output = io.StringIO()
        with redirect_stdout(output):
            code = main(["check", "--repo", str(self.repo), "--format", "sarif"])
        self.assertEqual(2, code)
        results = json.loads(output.getvalue())["runs"][0]["results"]
        finding = next(result for result in results if result["ruleId"] == "GHD010")
        uri = finding["locations"][0]["physicalLocation"]["artifactLocation"]["uri"]
        self.assertEqual("hooks%20space%20%25%20%23/pre-commit", uri)

    def _assert_report_rejects_hard_link(self, protected: Path) -> None:
        before = protected.read_bytes()
        output = Path(self._temporary.name) / "hard-linked-report.json"
        try:
            os.link(protected, output)
        except OSError:
            self.skipTest("hard links unavailable")
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            code = main(["check", "--repo", str(self.repo), "--output", str(output)])
        self.assertEqual(protected.read_bytes(), before)
        self.assertEqual(output.read_bytes(), before)
        self.assertEqual(code, 1)
        self.assertIn("hard links", stderr.getvalue())

    def test_report_cannot_replace_a_hard_link_to_a_hook(self) -> None:
        hook = self.write_hook("pre-commit", b"#!/bin/sh\nexit 0\n")
        self._assert_report_rejects_hard_link(hook)

    def test_report_cannot_replace_a_hard_link_to_git_config(self) -> None:
        self._assert_report_rejects_hard_link(self.repo / ".git" / "config")

    def test_report_cannot_follow_a_symbolic_link_to_an_external_file(self) -> None:
        protected = Path(self._temporary.name) / "original.txt"
        protected.write_bytes(b"preserve")
        output = Path(self._temporary.name) / "linked-report.json"
        try:
            output.symlink_to(protected)
        except OSError:
            self.skipTest("symbolic links unavailable")
        with redirect_stderr(io.StringIO()):
            self.assertEqual(main(["check", "--repo", str(self.repo), "--output", str(output)]), 1)
        self.assertEqual(protected.read_bytes(), b"preserve")

    def test_report_cannot_replace_hook_or_git_config(self) -> None:
        hook = self.write_hook("pre-commit", b"#!/bin/sh\nexit 0\n")
        for output in (hook, self.repo / ".git" / "config"):
            before = output.read_bytes()
            with redirect_stderr(io.StringIO()):
                code = main(["check", "--repo", str(self.repo), "--output", str(output)])
            self.assertEqual(code, 1)
            self.assertEqual(output.read_bytes(), before)

    def test_report_protects_custom_hooks_and_allows_a_regular_report(self) -> None:
        custom = self.repo / "custom-hooks"
        hook = self.write_hook("pre-commit", b"#!/bin/sh\nexit 0\n", directory=custom)
        self.git("config", "core.hooksPath", str(custom))
        before = hook.read_bytes()
        with redirect_stderr(io.StringIO()):
            self.assertEqual(main(["check", "--repo", str(self.repo), "--output", str(hook)]), 1)
        self.assertEqual(hook.read_bytes(), before)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main(["check", "--repo", str(self.repo), "--output", str(self.repo / "report.json"), "--format", "json"]), 0)

    def test_check_empty_repository_succeeds(self) -> None:
        with redirect_stdout(io.StringIO()):
            code = main(["check", "--repo", str(self.repo), "--color", "never"])
        self.assertEqual(0, code)

    def test_explain_missing_hook_uses_diagnostic_exit_code(self) -> None:
        with redirect_stdout(io.StringIO()):
            code = main(
                ["explain", "pre-commit", "--repo", str(self.repo), "--color", "never"]
            )
        self.assertEqual(2, code)

    def test_json_output_file_is_utf8_and_parseable(self) -> None:
        output = Path(self._temporary.name) / "report.json"
        code = main(
            [
                "check",
                "--repo",
                str(self.repo),
                "--format",
                "json",
                "--output",
                str(output),
            ]
        )
        self.assertEqual(0, code)
        payload = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual("1", payload["schema_version"])

    def test_non_repository_is_runtime_error(self) -> None:
        outside = Path(self._temporary.name) / "outside"
        outside.mkdir()
        with redirect_stderr(io.StringIO()):
            self.assertEqual(1, main(["check", "--repo", str(outside)]))

    def test_missing_git_executable_is_runtime_error(self) -> None:
        with redirect_stderr(io.StringIO()):
            self.assertEqual(
                1,
                main(
                    [
                        "check",
                        "--repo",
                        str(self.repo),
                        "--git",
                        "definitely-missing-git-hook-doctor-git",
                    ]
                ),
            )


if __name__ == "__main__":
    import unittest

    raise SystemExit(unittest.main())

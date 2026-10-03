from __future__ import annotations

import json
import io
from pathlib import Path
from contextlib import redirect_stderr, redirect_stdout

from git_hook_doctor.cli import main

from support import GitRepositoryTestCase


class CliTests(GitRepositoryTestCase):
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

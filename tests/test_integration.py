from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

from git_hook_doctor.doctor import diagnose
from git_hook_doctor.models import ConfigEntry, RepositoryInfo

from support import GitRepositoryTestCase


class DiagnosisIntegrationTests(GitRepositoryTestCase):
    def codes(self, report) -> set[str]:
        return {finding.code for finding in report.findings}

    def test_empty_repository_has_only_an_informational_result(self) -> None:
        report = diagnose(self.repo)
        self.assertIn("GHD001", self.codes(report))
        self.assertEqual(0, report.counts["error"])

    def test_explain_missing_hook_fails_with_exact_path(self) -> None:
        report = diagnose(self.repo, events=["pre-commit"])
        self.assertIn("GHD003", self.codes(report))
        expected = self.repo / ".git" / "hooks" / "pre-commit"
        actual = report.hooks[0].path
        self.assertIsNotNone(actual)
        assert actual is not None
        self.assertEqual(expected.name, actual.name)
        self.assertTrue(os.path.samefile(expected.parent, actual.parent))

    def test_valid_hook_is_ready(self) -> None:
        self.write_hook("pre-commit", b"#!/usr/bin/env python\nprint('ok')\n")
        report = diagnose(self.repo, events=["pre-commit"], platform_name=os.name)
        self.assertEqual("ready", report.hooks[0].status)
        self.assertEqual(0, report.counts["error"])

    def test_relative_core_hooks_path_is_the_effective_directory(self) -> None:
        custom = self.repo / ".githooks"
        self.git("config", "core.hooksPath", ".githooks")
        self.write_hook("pre-commit", b"#!/usr/bin/env python\n", directory=custom)
        report = diagnose(self.repo, events=["pre-commit"], platform_name=os.name)
        self.assertEqual(custom.resolve(), report.repository.hooks_dir.resolve())
        self.assertEqual(".githooks", report.core_hooks_path.value)
        self.assertEqual("ready", report.hooks[0].status)

    def test_receive_hook_resolves_relative_hooks_path_from_git_directory(self) -> None:
        self.git("config", "core.hooksPath", ".githooks")
        server_hooks = self.repo / ".git" / ".githooks"
        self.write_hook("pre-receive", b"#!/usr/bin/env python\n", directory=server_hooks)
        report = diagnose(self.repo, events=["pre-receive"], platform_name=os.name)
        self.assertEqual(
            (server_hooks / "pre-receive").resolve(), report.hooks[0].path.resolve()
        )
        self.assertEqual("ready", report.hooks[0].status)

    def test_client_hook_in_server_directory_is_reported_as_shadowed(self) -> None:
        self.git("config", "core.hooksPath", ".githooks")
        server_hooks = self.repo / ".git" / ".githooks"
        self.write_hook("pre-commit", b"#!/usr/bin/env python\n", directory=server_hooks)
        report = diagnose(self.repo)
        self.assertIn("GHD013", self.codes(report))

    def test_hook_in_old_directory_is_reported_as_shadowed(self) -> None:
        self.git("config", "core.hooksPath", ".githooks")
        self.write_hook("pre-commit", b"#!/usr/bin/env python\n")
        report = diagnose(self.repo)
        self.assertIn("GHD013", self.codes(report))

    def test_linked_worktree_reports_missing_relative_hooks_path(self) -> None:
        (self.repo / "tracked.txt").write_text("tracked\n", encoding="utf-8")
        self.git("add", "tracked.txt")
        self.git("commit", "-q", "-m", "seed")
        self.git("config", "core.hooksPath", ".githooks")
        linked = Path(self._temporary.name) / "linked"
        self.git("worktree", "add", "-q", "-b", "linked-test", str(linked))
        report = diagnose(linked)
        self.assertTrue(report.repository.is_linked_worktree)
        self.assertIn("GHD021", self.codes(report))

    def test_bare_repository_uses_its_own_hooks_directory(self) -> None:
        bare = Path(self._temporary.name) / "remote.git"
        bare.mkdir()
        self.git("init", "--bare", "-q", cwd=bare)
        report = diagnose(bare)
        self.assertTrue(report.repository.is_bare)
        self.assertEqual(bare.resolve(), report.repository.root.resolve())
        self.assertEqual((bare / "hooks").resolve(), report.repository.hooks_dir.resolve())

    def test_dev_null_disables_traditional_hooks_on_posix(self) -> None:
        self.git("config", "core.hooksPath", "/dev/null")
        report = diagnose(self.repo, platform_name="posix")
        self.assertIn("GHD002", self.codes(report))

    def test_windows_nul_is_not_treated_as_disabled_on_posix(self) -> None:
        self.git("config", "core.hooksPath", "NUL")
        report = diagnose(self.repo, platform_name="posix")
        self.assertNotIn("GHD002", self.codes(report))

    def git_255_repository(self) -> RepositoryInfo:
        return RepositoryInfo(
            root=self.repo,
            git_dir=self.repo / ".git",
            common_dir=self.repo / ".git",
            hooks_dir=self.repo / ".git" / "hooks",
            hook_working_dir=self.repo,
            git_executable="git",
            git_version=(2, 55, 0),
            git_version_text="2.55.0",
            is_bare=False,
            is_linked_worktree=False,
        )

    def test_ready_configured_hook_does_not_require_a_traditional_file(self) -> None:
        entries = [
            ConfigEntry("local", "file:.git/config", "hook.lint.command", "echo ok"),
            ConfigEntry("local", "file:.git/config", "hook.lint.event", "pre-commit"),
        ]
        with patch("git_hook_doctor.doctor.discover_repository", return_value=self.git_255_repository()), patch(
            "git_hook_doctor.doctor.read_relevant_config", return_value=entries
        ):
            report = diagnose(self.repo, events=["pre-commit"])
        self.assertNotIn("GHD003", self.codes(report))
        self.assertEqual(["configured"], [hook.source for hook in report.hooks])
        self.assertEqual("ready", report.hooks[0].status)

    def test_disabled_event_does_not_report_a_missing_hook_as_an_error(self) -> None:
        entries = [
            ConfigEntry(
                "local", "file:.git/config", "hook.pre-commit.enabled", "false"
            )
        ]
        with patch("git_hook_doctor.doctor.discover_repository", return_value=self.git_255_repository()), patch(
            "git_hook_doctor.doctor.read_relevant_config", return_value=entries
        ):
            report = diagnose(self.repo, events=["pre-commit"])
        self.assertNotIn("GHD003", self.codes(report))
        self.assertIn("GHD017", self.codes(report))
        self.assertEqual("disabled", report.hooks[0].status)


if __name__ == "__main__":
    import unittest

    raise SystemExit(unittest.main())

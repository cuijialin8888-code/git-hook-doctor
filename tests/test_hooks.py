from __future__ import annotations

import os
import stat
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from git_hook_doctor.config import ConfiguredHook, EventSettings
from git_hook_doctor.hooks import analyze_configured_hook, analyze_traditional_hook
from git_hook_doctor.models import ConfigEntry, RepositoryInfo


def fake_repository(root: Path, version: tuple[int, int, int] = (2, 55, 0)) -> RepositoryInfo:
    hooks = root / ".git" / "hooks"
    hooks.mkdir(parents=True, exist_ok=True)
    return RepositoryInfo(
        root=root,
        git_dir=root / ".git",
        common_dir=root / ".git",
        hooks_dir=hooks,
        hook_working_dir=root,
        git_executable="git",
        git_version=version,
        git_version_text=".".join(str(part) for part in version),
        is_bare=False,
        is_linked_worktree=False,
    )


def config_entry(key: str, value: str) -> ConfigEntry:
    return ConfigEntry("local", "file:.git/config", key, value)


class TraditionalHookTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory(prefix="git-hook-doctor-hook-")
        self.root = Path(self._temporary.name)
        self.repository = fake_repository(self.root)
        self.path = self.repository.hooks_dir / "pre-commit"

    def tearDown(self) -> None:
        self._temporary.cleanup()

    def write(self, data: bytes, *, executable: bool = True) -> None:
        self.path.write_bytes(data)
        mode = self.path.stat().st_mode
        if executable:
            self.path.chmod(mode | stat.S_IXUSR)
        else:
            self.path.chmod(mode & ~(stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH))

    def codes(self, platform_name: str = "posix") -> set[str]:
        result = analyze_traditional_hook(
            "pre-commit",
            self.path,
            self.repository,
            explicit=True,
            platform_name=platform_name,
        )
        return {finding.code for finding in result.findings}

    def test_valid_text_hook_is_ready(self) -> None:
        self.write(b"#!/usr/bin/env python\nprint('ok')\n")
        result = analyze_traditional_hook(
            "pre-commit", self.path, self.repository, explicit=True, platform_name=os.name
        )
        self.assertEqual("ready", result.status)
        self.assertEqual([], result.findings)

    def test_missing_hook_and_sample_are_explained(self) -> None:
        (self.repository.hooks_dir / "pre-commit.sample").write_text("sample", encoding="utf-8")
        self.assertEqual({"GHD003", "GHD004"}, self.codes())

    def test_filename_extension_is_not_treated_as_installed(self) -> None:
        (self.repository.hooks_dir / "pre-commit.sh").write_text("#!/bin/sh\n", encoding="utf-8")
        self.assertEqual({"GHD003", "GHD005"}, self.codes())

    def test_non_executable_hook_is_blocked_on_posix(self) -> None:
        self.write(b"#!/usr/bin/env python\n", executable=False)
        self.assertIn("GHD007", self.codes("posix"))

    def test_windows_does_not_invent_an_executable_bit_failure(self) -> None:
        self.write(b"#!/usr/bin/env python\n", executable=False)
        self.assertNotIn("GHD007", self.codes("nt"))

    def test_empty_text_bom_crlf_and_missing_interpreter(self) -> None:
        cases = [
            (b"", "GHD008"),
            (b"print('no shebang')\n", "GHD009"),
            (b"#!/usr/bin/env python\r\nprint('x')\r\n", "GHD010"),
            (b"\xef\xbb\xbf#!/usr/bin/env python\n", "GHD011"),
            (b"#!/usr/bin/env\n", "GHD012"),
            (b"#!/definitely/missing/git-hook-doctor\n", "GHD012"),
        ]
        for data, expected in cases:
            with self.subTest(expected=expected):
                self.write(data)
                self.assertIn(expected, self.codes("posix"))

    def test_native_binary_does_not_require_a_shebang(self) -> None:
        self.write(b"MZ\x00\x00binary")
        self.assertNotIn("GHD009", self.codes("nt"))

    def test_windows_accepts_exe_fallback(self) -> None:
        executable = self.repository.hooks_dir / "pre-commit.exe"
        executable.write_bytes(b"MZ\x00\x00binary")
        result = analyze_traditional_hook(
            "pre-commit",
            self.path,
            self.repository,
            explicit=True,
            platform_name="nt",
        )
        self.assertEqual("ready", result.status)
        self.assertEqual(executable, result.path)

    def test_posix_does_not_accept_exe_fallback(self) -> None:
        executable = self.repository.hooks_dir / "pre-commit.exe"
        executable.write_bytes(b"MZ\x00\x00binary")
        self.assertIn("GHD005", self.codes("posix"))


class ConfiguredHookTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory(prefix="git-hook-doctor-config-")
        self.root = Path(self._temporary.name)
        self.repository = fake_repository(self.root)

    def tearDown(self) -> None:
        self._temporary.cleanup()

    def hook(self, command: str | None = "echo ok", *, enabled: str | None = None) -> ConfiguredHook:
        hook = ConfiguredHook(name="lint")
        event = config_entry("hook.lint.event", "pre-commit")
        hook.events.append(("pre-commit", event))
        if command is not None:
            hook.command = config_entry("hook.lint.command", command)
        if enabled is not None:
            hook.enabled = config_entry("hook.lint.enabled", enabled)
        return hook

    def codes(self, hook: ConfiguredHook, repository: RepositoryInfo | None = None) -> set[str]:
        result = analyze_configured_hook(
            hook,
            "pre-commit",
            repository or self.repository,
            None,
            platform_name=os.name,
        )
        return {finding.code for finding in result.findings}

    def test_git_before_254_cannot_run_configured_hooks(self) -> None:
        repository = replace(self.repository, git_version=(2, 53, 0), git_version_text="2.53.0")
        self.assertIn("GHD014", self.codes(self.hook(), repository))

    def test_disabled_configured_hook_is_reported_without_running(self) -> None:
        result = analyze_configured_hook(
            self.hook(enabled="false"),
            "pre-commit",
            self.repository,
            None,
            platform_name=os.name,
        )
        self.assertEqual("disabled", result.status)
        self.assertIn("GHD016", {finding.code for finding in result.findings})

    def test_disabled_configured_hook_does_not_require_a_command(self) -> None:
        result = analyze_configured_hook(
            self.hook(command=None, enabled="false"),
            "pre-commit",
            self.repository,
            None,
            platform_name=os.name,
        )
        self.assertEqual("disabled", result.status)
        self.assertNotIn("GHD015", {finding.code for finding in result.findings})

    def test_missing_command_is_blocked(self) -> None:
        self.assertIn("GHD015", self.codes(self.hook(command=None)))

    def test_missing_path_command_is_blocked(self) -> None:
        self.assertIn("GHD018", self.codes(self.hook(command="./missing-linter")))

    def test_existing_relative_command_is_ready(self) -> None:
        target = self.root / "lint"
        target.write_text("ok", encoding="utf-8")
        result = analyze_configured_hook(
            self.hook(command="./lint"),
            "pre-commit",
            self.repository,
            None,
            platform_name=os.name,
        )
        self.assertEqual("ready", result.status)

    def test_command_preview_omits_arguments_and_environment_secrets(self) -> None:
        target = self.root / "lint"
        target.write_text("ok", encoding="utf-8")
        secret = "not-for-reports-12345"
        result = analyze_configured_hook(
            self.hook(command=f"TOKEN={secret} ./lint --api-key {secret}"),
            "pre-commit",
            self.repository,
            None,
            platform_name=os.name,
        )
        self.assertEqual("ready", result.status)
        self.assertEqual("./lint ...", result.command)
        self.assertNotIn(secret, str(result.to_dict(self.root)))

    def test_shell_command_body_is_not_echoed(self) -> None:
        secret = "not-for-reports-67890"
        result = analyze_configured_hook(
            self.hook(command=f"echo {secret} | custom-check"),
            "pre-commit",
            self.repository,
            None,
            platform_name=os.name,
        )
        self.assertEqual("<shell command omitted>", result.command)
        self.assertNotIn(secret, str(result.to_dict(self.root)))

    def test_receive_hook_relative_command_resolves_from_git_directory(self) -> None:
        target = self.repository.git_dir / "server-lint"
        target.write_text("ok", encoding="utf-8")
        hook = ConfiguredHook(name="receive-lint")
        event = config_entry("hook.receive-lint.event", "pre-receive")
        hook.events.append(("pre-receive", event))
        hook.command = config_entry("hook.receive-lint.command", "./server-lint")
        result = analyze_configured_hook(
            hook,
            "pre-receive",
            self.repository,
            None,
            platform_name=os.name,
        )
        self.assertEqual("ready", result.status)

    def test_parallel_setting_needs_git_255(self) -> None:
        hook = self.hook()
        hook.parallel = config_entry("hook.lint.parallel", "true")
        repository = replace(self.repository, git_version=(2, 54, 0), git_version_text="2.54.0")
        self.assertIn("GHD020", self.codes(hook, repository))

    def test_event_disabled_on_git_255(self) -> None:
        settings = EventSettings(enabled=config_entry("hook.pre-commit.enabled", "false"))
        result = analyze_configured_hook(
            self.hook(),
            "pre-commit",
            self.repository,
            settings,
            platform_name=os.name,
        )
        self.assertEqual("disabled", result.status)
        self.assertIn("GHD017", {finding.code for finding in result.findings})


if __name__ == "__main__":
    raise SystemExit(unittest.main())

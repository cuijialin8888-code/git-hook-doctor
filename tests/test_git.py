from __future__ import annotations

from pathlib import Path

from git_hook_doctor.git import (
    _parse_config_output,
    discover_repository,
    parse_git_version,
    read_relevant_config,
)

from support import GitRepositoryTestCase


class GitUtilitiesTests(GitRepositoryTestCase):
    def test_parse_git_version_handles_vendor_suffix(self) -> None:
        self.assertEqual((2, 53, 0), parse_git_version("git version 2.53.0.windows.3"))
        self.assertEqual((2, 54, 0), parse_git_version("git version 2.54"))

    def test_parse_config_output_with_scope(self) -> None:
        raw = (
            b"local\0file:.git/config\0hook.linter.command\n./lint --fast\0"
            b"global\0file:C:/Users/me/.gitconfig\0hook.linter.event\npre-commit\0"
        )
        entries = _parse_config_output(raw, with_scope=True)
        self.assertEqual(2, len(entries))
        self.assertEqual("local", entries[0].scope)
        self.assertEqual("hook.linter.command", entries[0].key)
        self.assertEqual("./lint --fast", entries[0].value)

    def test_parse_config_output_without_scope(self) -> None:
        raw = b"file:.git/config\0core.hookspath\n.githooks\0"
        entries = _parse_config_output(raw, with_scope=False)
        self.assertEqual("unknown", entries[0].scope)
        self.assertEqual(".githooks", entries[0].value)

    def test_discover_repository_uses_effective_hooks_path(self) -> None:
        self.git("config", "core.hooksPath", ".githooks")
        repository = discover_repository(self.repo)
        self.assertEqual((self.repo / ".githooks").resolve(), repository.hooks_dir.resolve())
        self.assertEqual(self.repo.resolve(), repository.root.resolve())

    def test_read_relevant_config_preserves_provenance_and_order(self) -> None:
        self.git("config", "core.hooksPath", ".githooks")
        self.git("config", "hook.linter.command", "./lint")
        self.git("config", "--add", "hook.linter.event", "pre-commit")
        self.git("config", "--add", "hook.linter.event", "pre-push")
        repository = discover_repository(self.repo)
        entries = read_relevant_config(repository)
        values = [(entry.key.lower(), entry.value) for entry in entries]
        self.assertIn(("core.hookspath", ".githooks"), values)
        self.assertEqual(
            ["pre-commit", "pre-push"],
            [entry.value for entry in entries if entry.key.lower() == "hook.linter.event"],
        )
        self.assertTrue(all(entry.origin for entry in entries))


if __name__ == "__main__":
    raise SystemExit(unittest.main())

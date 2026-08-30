from __future__ import annotations

import unittest

from git_hook_doctor.config import parse_config
from git_hook_doctor.models import ConfigEntry


def entry(key: str, value: str, scope: str = "local") -> ConfigEntry:
    return ConfigEntry(scope=scope, origin="file:.git/config", key=key, value=value)


class ConfigParserTests(unittest.TestCase):
    def test_last_command_wins_and_events_accumulate(self) -> None:
        parsed = parse_config(
            [
                entry("hook.lint.command", "old-lint"),
                entry("hook.lint.event", "pre-commit"),
                entry("hook.lint.command", "new-lint"),
                entry("hook.lint.event", "pre-push"),
            ]
        )
        hook = parsed.hooks["lint"]
        self.assertEqual("new-lint", hook.command.value)
        self.assertEqual(["pre-commit", "pre-push"], [value for value, _ in hook.events])

    def test_empty_event_resets_previous_values(self) -> None:
        parsed = parse_config(
            [
                entry("hook.lint.event", "pre-commit", "global"),
                entry("hook.lint.event", "", "local"),
                entry("hook.lint.event", "pre-push", "local"),
            ]
        )
        self.assertEqual(["pre-push"], [value for value, _ in parsed.hooks["lint"].events])

    def test_event_settings_are_not_misread_as_friendly_hooks(self) -> None:
        parsed = parse_config(
            [
                entry("hook.pre-commit.enabled", "false"),
                entry("hook.pre-push.jobs", "3"),
                entry("hook.jobs", "2"),
            ]
        )
        self.assertFalse(parsed.event_settings["pre-commit"].is_enabled)
        self.assertEqual("3", parsed.event_settings["pre-push"].jobs.value)
        self.assertEqual("2", parsed.global_jobs.value)
        self.assertNotIn("pre-commit", parsed.hooks)

    def test_core_hooks_path_is_last_effective_value(self) -> None:
        parsed = parse_config(
            [
                entry("core.hookspath", ".global-hooks", "global"),
                entry("core.hookspath", ".repo-hooks", "local"),
            ]
        )
        self.assertEqual(".repo-hooks", parsed.core_hooks_path.value)
        self.assertEqual("local", parsed.core_hooks_path.scope)


if __name__ == "__main__":
    raise SystemExit(unittest.main())

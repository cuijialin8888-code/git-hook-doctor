from __future__ import annotations

from dataclasses import dataclass, field

from .git import bool_value
from .models import ConfigEntry


KNOWN_HOOK_EVENTS = (
    "applypatch-msg",
    "pre-applypatch",
    "post-applypatch",
    "pre-commit",
    "pre-merge-commit",
    "prepare-commit-msg",
    "commit-msg",
    "post-commit",
    "pre-rebase",
    "post-checkout",
    "post-merge",
    "pre-push",
    "pre-receive",
    "update",
    "proc-receive",
    "post-receive",
    "post-update",
    "reference-transaction",
    "push-to-checkout",
    "pre-auto-gc",
    "post-rewrite",
    "sendemail-validate",
    "fsmonitor-watchman",
    "p4-changelist",
    "p4-prepare-changelist",
    "p4-post-changelist",
    "p4-pre-submit",
    "post-index-change",
)

KNOWN_HOOK_EVENT_SET = frozenset(KNOWN_HOOK_EVENTS)

SERVER_HOOK_EVENTS = frozenset(
    {
        "pre-receive",
        "update",
        "proc-receive",
        "post-receive",
        "post-update",
        "push-to-checkout",
    }
)


@dataclass
class ConfiguredHook:
    name: str
    events: list[tuple[str, ConfigEntry]] = field(default_factory=list)
    command: ConfigEntry | None = None
    enabled: ConfigEntry | None = None
    parallel: ConfigEntry | None = None

    @property
    def is_enabled(self) -> bool:
        return bool_value(self.enabled.value) if self.enabled else True


@dataclass
class EventSettings:
    enabled: ConfigEntry | None = None
    jobs: ConfigEntry | None = None

    @property
    def is_enabled(self) -> bool:
        return bool_value(self.enabled.value) if self.enabled else True


@dataclass
class ParsedConfig:
    core_hooks_path: ConfigEntry | None
    hooks: dict[str, ConfiguredHook]
    event_settings: dict[str, EventSettings]
    global_jobs: ConfigEntry | None


def parse_config(entries: list[ConfigEntry]) -> ParsedConfig:
    core_hooks_path: ConfigEntry | None = None
    hooks: dict[str, ConfiguredHook] = {}
    event_settings: dict[str, EventSettings] = {}
    global_jobs: ConfigEntry | None = None

    friendly_names: set[str] = set()
    for entry in entries:
        key = entry.key
        lower = key.lower()
        if lower == "core.hookspath":
            core_hooks_path = entry
            continue
        if not lower.startswith("hook."):
            continue
        rest = key[5:]
        if "." not in rest:
            continue
        name, prop = rest.rsplit(".", 1)
        if prop.lower() in {"event", "command", "parallel"}:
            friendly_names.add(name)
        elif prop.lower() == "enabled" and name not in KNOWN_HOOK_EVENT_SET:
            friendly_names.add(name)

    for entry in entries:
        key = entry.key
        lower = key.lower()
        if not lower.startswith("hook."):
            continue
        rest = key[5:]
        if rest.lower() == "jobs":
            global_jobs = entry
            continue
        if "." not in rest:
            continue
        name, prop = rest.rsplit(".", 1)
        prop = prop.lower()

        if prop in {"enabled", "jobs"} and name in KNOWN_HOOK_EVENT_SET and name not in friendly_names:
            settings = event_settings.setdefault(name, EventSettings())
            if prop == "enabled":
                settings.enabled = entry
            else:
                settings.jobs = entry
            continue

        if prop not in {"event", "command", "enabled", "parallel"}:
            continue
        hook = hooks.setdefault(name, ConfiguredHook(name=name))
        if prop == "event":
            if entry.value == "":
                hook.events.clear()
            else:
                hook.events.append((entry.value, entry))
        elif prop == "command":
            hook.command = entry
        elif prop == "enabled":
            hook.enabled = entry
        elif prop == "parallel":
            hook.parallel = entry

    return ParsedConfig(
        core_hooks_path=core_hooks_path,
        hooks=hooks,
        event_settings=event_settings,
        global_jobs=global_jobs,
    )

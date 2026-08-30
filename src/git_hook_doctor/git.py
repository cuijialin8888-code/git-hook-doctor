from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from .models import ConfigEntry, RepositoryInfo


class GitInvocationError(RuntimeError):
    def __init__(self, message: str, *, stderr: str = "", returncode: int = 1) -> None:
        super().__init__(message)
        self.stderr = stderr
        self.returncode = returncode


def _environment() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("LC_ALL", "C")
    env.setdefault("LANG", "C")
    return env


def _run(
    git_executable: str,
    cwd: Path,
    args: list[str],
    *,
    allowed: tuple[int, ...] = (0,),
) -> subprocess.CompletedProcess[bytes]:
    try:
        completed = subprocess.run(
            [git_executable, "-C", str(cwd), *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            env=_environment(),
        )
    except FileNotFoundError as exc:
        raise GitInvocationError(f"Git executable not found: {git_executable}") from exc
    if completed.returncode not in allowed:
        stderr = completed.stderr.decode("utf-8", "replace").strip()
        raise GitInvocationError(
            stderr or f"Git command failed with exit code {completed.returncode}",
            stderr=stderr,
            returncode=completed.returncode,
        )
    return completed


def _text(completed: subprocess.CompletedProcess[bytes]) -> str:
    return completed.stdout.decode("utf-8", "surrogateescape").strip()


def _absolute_from_git(value: str, base: Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = base / path
    return Path(os.path.abspath(path))


def parse_git_version(text: str) -> tuple[int, int, int]:
    match = re.search(r"(?<!\d)(\d+)\.(\d+)(?:\.(\d+))?", text)
    if not match:
        return (0, 0, 0)
    return tuple(int(part or 0) for part in match.groups())  # type: ignore[return-value]


def discover_repository(path: Path, git_executable: str = "git") -> RepositoryInfo:
    start = path.expanduser()
    if start.is_file():
        start = start.parent
    start = Path(os.path.abspath(start))
    if not start.exists():
        raise GitInvocationError(f"Repository path does not exist: {start}")

    version_process = _run(git_executable, start, ["--version"])
    version_text = _text(version_process)
    version = parse_git_version(version_text)

    try:
        bare = _text(_run(git_executable, start, ["rev-parse", "--is-bare-repository"])) == "true"
    except GitInvocationError as exc:
        raise GitInvocationError(f"Not a Git repository: {start}", stderr=exc.stderr) from exc

    git_dir_raw = _text(
        _run(git_executable, start, ["rev-parse", "--path-format=absolute", "--git-dir"])
    )
    git_dir = _absolute_from_git(git_dir_raw, start)

    common_raw = _text(
        _run(git_executable, start, ["rev-parse", "--path-format=absolute", "--git-common-dir"])
    )
    common_dir = _absolute_from_git(common_raw, start)

    if bare:
        root = git_dir
        hook_working_dir = git_dir
    else:
        root_raw = _text(_run(git_executable, start, ["rev-parse", "--show-toplevel"]))
        root = _absolute_from_git(root_raw, start)
        hook_working_dir = root

    hooks_raw = _text(_run(git_executable, start, ["rev-parse", "--git-path", "hooks"]))
    hooks_dir = _absolute_from_git(hooks_raw, hook_working_dir)

    return RepositoryInfo(
        root=root,
        git_dir=git_dir,
        common_dir=common_dir,
        hooks_dir=hooks_dir,
        hook_working_dir=hook_working_dir,
        git_executable=git_executable,
        git_version=version,
        git_version_text=version_text.removeprefix("git version "),
        is_bare=bare,
        is_linked_worktree=git_dir != common_dir,
    )


def _decode(value: bytes) -> str:
    return value.decode("utf-8", "surrogateescape")


def _parse_config_output(data: bytes, *, with_scope: bool) -> list[ConfigEntry]:
    tokens = data.split(b"\0")
    if tokens and tokens[-1] == b"":
        tokens.pop()
    width = 3 if with_scope else 2
    if not tokens:
        return []
    if len(tokens) % width:
        raise GitInvocationError("Could not parse Git config provenance output")

    entries: list[ConfigEntry] = []
    for index in range(0, len(tokens), width):
        if with_scope:
            scope = _decode(tokens[index])
            origin = _decode(tokens[index + 1])
            pair = tokens[index + 2]
        else:
            scope = "unknown"
            origin = _decode(tokens[index])
            pair = tokens[index + 1]
        key_bytes, separator, value_bytes = pair.partition(b"\n")
        if not separator:
            key_bytes, separator, value_bytes = pair.partition(b"\r")
        if not separator:
            raise GitInvocationError("Could not split a Git config key/value record")
        key = _decode(key_bytes).rstrip("\r")
        value = _decode(value_bytes)
        entries.append(ConfigEntry(scope=scope, origin=origin, key=key, value=value))
    return entries


def read_relevant_config(repository: RepositoryInfo) -> list[ConfigEntry]:
    pattern = r"^(core\.hookspath|hook\.)"
    args = ["config", "--null", "--show-origin", "--show-scope", "--get-regexp", pattern]
    completed = _run(
        repository.git_executable,
        repository.root,
        args,
        allowed=(0, 1, 129),
    )
    if completed.returncode == 1:
        return []
    if completed.returncode == 0:
        return _parse_config_output(completed.stdout, with_scope=True)

    fallback = _run(
        repository.git_executable,
        repository.root,
        ["config", "--null", "--show-origin", "--get-regexp", pattern],
        allowed=(0, 1),
    )
    if fallback.returncode == 1:
        return []
    return _parse_config_output(fallback.stdout, with_scope=False)


def bool_value(value: str, default: bool = True) -> bool:
    normalized = value.strip().lower()
    if normalized in {"true", "yes", "on", "1"}:
        return True
    if normalized in {"false", "no", "off", "0", ""}:
        return False
    return default

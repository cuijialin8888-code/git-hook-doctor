"""Create a disposable broken hook and run a read-only diagnosis."""

from __future__ import annotations

import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path


def run(*args: str, cwd: Path) -> None:
    subprocess.run(args, cwd=cwd, check=True)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="git-hook-doctor-demo-") as temporary:
        repo = Path(temporary) / "demo-repo"
        repo.mkdir()
        run("git", "init", "-q", cwd=repo)
        run("git", "config", "core.hooksPath", ".githooks", cwd=repo)
        hooks = repo / ".githooks"
        hooks.mkdir()
        hook = hooks / "pre-commit"
        hook.write_bytes(b"#!/usr/bin/env definitely-not-installed\r\necho demo\r\n")
        if os.name != "nt":
            hook.chmod(hook.stat().st_mode | stat.S_IXUSR)

        command = [
            sys.executable,
            "-m",
            "git_hook_doctor",
            "explain",
            "pre-commit",
            "--repo",
            str(repo),
            "--color",
            "always",
            "--fail-on",
            "never",
        ]
        print("$ git-hook-doctor explain pre-commit", flush=True)
        return subprocess.run(command, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())

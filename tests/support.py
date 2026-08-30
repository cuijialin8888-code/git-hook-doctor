from __future__ import annotations

import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


class GitRepositoryTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory(prefix="git-hook-doctor-test-")
        self.repo = Path(self._temporary.name) / "repo"
        self.repo.mkdir()
        self.git("init", "-q")
        self.git("config", "user.name", "Git Hook Doctor Tests")
        self.git("config", "user.email", "tests@example.invalid")

    def tearDown(self) -> None:
        self._temporary.cleanup()

    def git(self, *args: str, cwd: Path | None = None) -> str:
        completed = subprocess.run(
            ["git", "-C", str(cwd or self.repo), *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            env=os.environ.copy(),
        )
        if completed.returncode:
            self.fail(completed.stderr.decode("utf-8", "replace"))
        return completed.stdout.decode("utf-8", "surrogateescape").strip()

    def hook_path(self, event: str, directory: Path | None = None) -> Path:
        hooks = directory or (self.repo / ".git" / "hooks")
        hooks.mkdir(parents=True, exist_ok=True)
        return hooks / event

    def write_hook(self, event: str, data: bytes, *, directory: Path | None = None) -> Path:
        path = self.hook_path(event, directory)
        path.write_bytes(data)
        if os.name != "nt":
            path.chmod(path.stat().st_mode | stat.S_IXUSR)
        return path

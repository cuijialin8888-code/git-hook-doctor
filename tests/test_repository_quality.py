from __future__ import annotations

import json
import re
import struct
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from git_hook_doctor import __version__


ROOT = Path(__file__).resolve().parents[1]


class RepositoryQualityTests(unittest.TestCase):
    def test_versions_and_release_date_are_synchronized(self) -> None:
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertIn(f'version = "{__version__}"', pyproject)
        self.assertIn(f"## [{__version__}] - 2026-08-31", changelog)
        self.assertIn(f"releases/download/v{__version__}", (ROOT / "README.md").read_text(encoding="utf-8"))

    def test_all_local_markdown_links_exist(self) -> None:
        markdown_link = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
        html_link = re.compile(r"(?:href|src)=\"([^\"]+)\"")
        missing: list[str] = []
        for document in ROOT.rglob("*.md"):
            text = document.read_text(encoding="utf-8")
            targets = markdown_link.findall(text) + html_link.findall(text)
            for target in targets:
                target = target.strip().strip("<>").split("#", 1)[0]
                if not target or "://" in target or target.startswith(("mailto:", "#")):
                    continue
                resolved = (document.parent / target).resolve()
                if not resolved.exists():
                    missing.append(f"{document.relative_to(ROOT)} -> {target}")
        self.assertEqual([], missing)

    def test_workflow_actions_are_immutably_pinned(self) -> None:
        unpinned: list[str] = []
        for workflow in (ROOT / ".github" / "workflows").glob("*.yml"):
            for line_number, line in enumerate(workflow.read_text(encoding="utf-8").splitlines(), 1):
                match = re.search(r"uses:\s*([^\s#]+)", line)
                if not match or match.group(1).startswith("./"):
                    continue
                reference = match.group(1).rsplit("@", 1)[-1]
                if not re.fullmatch(r"[0-9a-f]{40}", reference):
                    unpinned.append(f"{workflow.name}:{line_number} {match.group(1)}")
        self.assertEqual([], unpinned)

    def test_png_assets_have_expected_dimensions(self) -> None:
        expected = {
            "logo.png": (512, 512),
            "demo.png": (1200, 640),
            "social-preview.png": (1280, 640),
        }
        for name, dimensions in expected.items():
            with self.subTest(name=name):
                data = (ROOT / "assets" / name).read_bytes()
                self.assertEqual(b"\x89PNG\r\n\x1a\n", data[:8])
                width, height = struct.unpack(">II", data[16:24])
                self.assertEqual(dimensions, (width, height))

    def test_svg_assets_are_well_formed_and_accessibly_titled(self) -> None:
        for asset in (ROOT / "assets").glob("*.svg"):
            with self.subTest(asset=asset.name):
                root = ET.parse(asset).getroot()
                titles = root.findall("{http://www.w3.org/2000/svg}title")
                descriptions = root.findall("{http://www.w3.org/2000/svg}desc")
                self.assertTrue(titles)
                self.assertTrue(descriptions)

    def test_every_emitted_rule_has_documentation(self) -> None:
        source = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (ROOT / "src" / "git_hook_doctor").glob("*.py")
        )
        rules = (ROOT / "docs" / "rules.md").read_text(encoding="utf-8")
        emitted = set(re.findall(r'"(GHD\d{3})"', source))
        documented = set(re.findall(r"### (GHD\d{3})", rules))
        self.assertEqual(emitted, documented)

    def test_json_schema_preserves_read_only_contract(self) -> None:
        schema = json.loads((ROOT / "schemas" / "report.schema.json").read_text(encoding="utf-8"))
        safety = schema["properties"]["safety"]["properties"]
        self.assertIs(safety["read_only"]["const"], True)
        self.assertIs(safety["hooks_executed"]["const"], False)


if __name__ == "__main__":
    raise SystemExit(unittest.main())

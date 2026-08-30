from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .doctor import diagnose
from .git import GitInvocationError
from .models import Severity
from .reporters import render


def _common_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--repo",
        type=Path,
        default=Path.cwd(),
        help="repository or path inside it (default: current directory)",
    )
    common.add_argument(
        "--git",
        default="git",
        metavar="EXECUTABLE",
        help="Git executable to inspect (default: git from PATH)",
    )
    common.add_argument(
        "--format",
        choices=("text", "json", "markdown", "sarif"),
        default="text",
        help="report format (default: text)",
    )
    common.add_argument(
        "--output",
        type=Path,
        help="write the report to a file instead of stdout",
    )
    common.add_argument(
        "--fail-on",
        choices=("never", "warning", "error"),
        default="error",
        help="exit 2 when this severity is present (default: error)",
    )
    common.add_argument(
        "--color",
        choices=("auto", "always", "never"),
        default="auto",
        help="ANSI color policy for text output",
    )
    return common


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="git-hook-doctor",
        description="Explain why a Git hook will or will not run without executing it.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)
    common = _common_parser()

    check = subparsers.add_parser(
        "check",
        parents=[common],
        help="inspect discovered hooks, or only the named events",
    )
    check.add_argument("events", nargs="*", metavar="HOOK", help="hook event names to inspect")

    explain = subparsers.add_parser(
        "explain",
        parents=[common],
        help="explain one hook event, including a missing hook",
    )
    explain.add_argument("event", metavar="HOOK", help="hook event name, for example pre-commit")
    return parser


def _threshold(value: str) -> Severity | None:
    return None if value == "never" else Severity.parse(value)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    events = args.events if args.command == "check" else [args.event]
    try:
        report = diagnose(args.repo, events=events, git_executable=args.git)
    except (GitInvocationError, ValueError, OSError) as exc:
        print(f"git-hook-doctor: {exc}", file=sys.stderr)
        return 1

    use_color = args.format == "text" and (
        args.color == "always" or (args.color == "auto" and sys.stdout.isatty() and not args.output)
    )
    content = render(report, args.format, color=use_color)
    if args.output:
        try:
            args.output.write_text(content, encoding="utf-8", newline="\n")
        except OSError as exc:
            print(f"git-hook-doctor: could not write {args.output}: {exc}", file=sys.stderr)
            return 1
    else:
        sys.stdout.write(content)
    return 2 if report.should_fail(_threshold(args.fail_on)) else 0


if __name__ == "__main__":
    raise SystemExit(main())

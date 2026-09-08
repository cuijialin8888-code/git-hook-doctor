# Changelog

All notable changes use [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) structure. The project follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Security

- Pin every Action in copyable workflow examples to an immutable commit SHA and test the invariant.

## [0.1.0] - 2026-08-31

### Added

- Read-only diagnosis of effective traditional Git hook paths.
- File, symlink, executable-bit, exact-name, sample, BOM, CRLF, shebang, and interpreter checks.
- Provenance-aware parsing of `core.hooksPath` and configured hooks.
- Git 2.54 configured-hook and Git 2.55 event/parallel compatibility checks.
- Linked-worktree and shadowed-install diagnostics.
- Text, JSON, Markdown, and SARIF reports with stable rule IDs.
- Cross-platform CLI, Composite Action, examples, and release automation.

[Unreleased]: https://github.com/cuijialin8888-code/git-hook-doctor/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/cuijialin8888-code/git-hook-doctor/releases/tag/v0.1.0

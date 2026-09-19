# Maintenance checklist

Keep Git Hook Doctor read-only and focused on explaining whether hooks are configured to start.

## Routine checks

- Never execute, source, or invoke a hook or configured command while inspecting it.
- Keep traditional-hook and configured-hook behavior documented together with stable rule IDs and fixtures.
- Add regression coverage for Git-version, worktree, path, encoding, and interpreter edge cases before changing detection.
- For releases, validate the wheel, source distribution, checksum assets, and the exact public CI result.

## Review log

- 2026-09-12: reviewed public `main`, open Issues/PRs, and recent Actions; no open Issues/PRs were present, and the latest main-branch CI run (`34177317188`) completed successfully.

- 2026-09-19: reviewed public `main`, open Issues/PRs, and recent Actions; no open Issues/PRs were present, and the latest main-branch CI run (`34675592639`) and configured GitHub Actions update run (`34885701493`) completed successfully.

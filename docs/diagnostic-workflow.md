# Evidence-first diagnostic workflow

Use this workflow when a Git hook appears not to run. Git Hook Doctor inspects effective paths and configuration; it never invokes a hook or changes the repository.

Start with `git-hook-doctor explain pre-commit` and `git-hook-doctor check`. For another checkout, keep the target explicit with `git-hook-doctor explain pre-push --repo ../my-project`.

Confirm the effective hook directory reported by Git, then follow `core.hooksPath`, relative-path provenance, linked-worktree layout, event names, exact filenames, executable bits, symlinks, sample suffixes, BOM/CRLF, shebangs, and interpreter availability. For configured hooks, compare the Git version with the configured-hook guide.

Use `--fail-on warning` for a strict CI gate or `--fail-on never` for inventory. JSON and Markdown reports are useful for review, but a clean static report does not prove that a GUI client, PATH, mount policy, or runtime environment will execute the hook.
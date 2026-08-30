# How Git Hook Doctor resolves evidence

Git Hook Doctor follows Git's own resolution before it inspects a file. It does not guess that `.git/hooks` is always correct.

## 1. Establish repository topology

The tool asks Git for:

```console
git rev-parse --is-bare-repository
git rev-parse --path-format=absolute --git-dir
git rev-parse --path-format=absolute --git-common-dir
git rev-parse --show-toplevel
```

The separate Git directory and common directory reveal linked worktrees. In a non-bare repository, Git runs most client hooks with the worktree root as the working directory. Receive-side hooks run in the Git directory.

## 2. Ask Git for the effective hook directory

```console
git rev-parse --git-path hooks
```

This honors `core.hooksPath`. Git's documentation says that a relative `core.hooksPath` is relative to the directory where hooks run, not necessarily to the config file that contains the value. That distinction is why a path can work in the main checkout and disappear in a linked worktree.

Git Hook Doctor resolves a relative result from the same documented working directory and keeps the original config scope and origin in the report.

## 3. Read relevant config with provenance

```console
git config --null --show-origin --show-scope --get-regexp \
  '^(core\.hookspath|hook\.)'
```

Git performs the include and precedence logic. The tool consumes the ordered result; it does not reimplement `.gitconfig` parsing.

The parser applies Git's configured-hook rules:

- the last `hook.<name>.command` wins;
- `hook.<name>.event` accumulates;
- an empty event value clears earlier events;
- per-hook and event-level enable switches are distinct;
- config scope and origin stay attached to the effective values.

## 4. Inspect without execution

Traditional hooks are checked at their exact resolved path. Only the first 8 KiB are needed for startup diagnostics. The tool looks at file type, symlink state, POSIX mode, byte zero, first-line ending, shebang, and interpreter availability.

Configured commands are never passed to a shell. A command is resolved only when its first token is statically unambiguous. Shell one-liners are left uninterpreted to avoid pretending that static parsing can reproduce shell semantics.

## 5. Report bounded conclusions

`ready` means the inspected startup conditions passed. It does not mean the hook will return zero, is safe, or behaves correctly. `blocked` means at least one inspected condition prevents or invalidates startup. `disabled` means a supported Git config switch prevents execution. `warning` means the hook is expected to run but a compatibility or placement risk remains.

No diagnostic path invokes `git hook run`, `git commit`, `git push`, or a hook command.

## Primary references

- [githooks documentation](https://git-scm.com/docs/githooks)
- [`core.hooksPath`](https://git-scm.com/docs/git-config#Documentation/git-config.txt-corehooksPath)
- [`git rev-parse --git-path`](https://git-scm.com/docs/git-rev-parse#Documentation/git-rev-parse.txt---git-pathltpathgt)
- [`git hook`](https://git-scm.com/docs/git-hook)
- [Git 2.54 release notes](https://github.com/git/git/blob/master/Documentation/RelNotes/2.54.0.adoc)
- [Git 2.55 release notes](https://github.com/git/git/blob/master/Documentation/RelNotes/2.55.0.adoc)

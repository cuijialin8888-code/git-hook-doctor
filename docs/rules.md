# Rule reference

Rule IDs are stable once released. Severity describes the default diagnostic impact; callers can choose the CI threshold with `--fail-on`.

## ghd001

### GHD001 — No hooks discovered (`info`)

No traditional hook files or configured hook events were found. Use `explain <event>` when a specific hook was expected.

## ghd002

### GHD002 — Traditional hooks disabled (`warning`)

The effective `core.hooksPath` is `/dev/null`, `NUL`, or `NUL:`. Configured hooks may still run on supported Git versions.

## ghd003

### GHD003 — Hook file missing (`error`)

An explicitly requested event has no traditional file at Git's effective path and no other runnable source explains the event.

## ghd004

### GHD004 — Sample only (`warning`)

`<event>.sample` exists, but Git does not run sample files.

## ghd005

### GHD005 — Wrong filename (`error`)

A file such as `pre-commit.sh` exists while Git looks for the exact extensionless name `pre-commit`. Git for Windows' native `.exe` fallback is recognized and is not reported by this rule.

## ghd006

### GHD006 — Invalid file or symlink (`error`)

The effective hook path is not a regular file or points through a broken symlink.

## ghd007

### GHD007 — Not executable (`error`)

On a platform with POSIX executable bits, the hook has no execute bit and Git ignores it.

## ghd008

### GHD008 — Empty hook (`error`)

The hook file contains no program.

## ghd009

### GHD009 — Missing shebang (`error`)

An extensionless text hook has no interpreter declaration at byte zero.

## ghd010

### GHD010 — CRLF shebang (`error`)

The first line ends in CRLF. The carriage return commonly becomes part of the interpreter name or its argument.

## ghd011

### GHD011 — BOM before shebang (`error`)

A UTF-8 byte-order mark appears before `#!`, so the operating system does not see a shebang at byte zero.

## ghd012

### GHD012 — Interpreter unavailable (`error`)

The shebang is invalid, has no `/usr/bin/env` target, or selects an interpreter that cannot be resolved in the inspected environment.

## ghd013

### GHD013 — Shadowed hook install (`warning`)

A hook-like file exists in a common directory, but Git resolves that event to another path.

## ghd014

### GHD014 — Configured hook unsupported (`error`)

`hook.<name>.event/command` is present but the selected Git is older than 2.54 and will not run configured hooks.

## ghd015

### GHD015 — Configured hook has no command (`error`)

The named hook has an event but no non-empty effective command.

## ghd016

### GHD016 — Configured hook disabled (`info`)

`hook.<name>.enabled=false` intentionally disables the named hook.

## ghd017

### GHD017 — Event disabled (`info`)

On Git 2.55+, `hook.<event>.enabled=false` intentionally disables every hook source for the event.

## ghd018

### GHD018 — Configured command unresolved (`error`)

The statically unambiguous first command token is neither an existing path nor an executable on PATH.

## ghd019

### GHD019 — Friendly-name collision (`error`)

A configured hook's friendly name equals a known Git event name, which current Git rejects as ambiguous.

## ghd020

### GHD020 — Newer hook setting unsupported (`warning`)

An event-level or parallelism setting requires Git 2.55+, but the selected Git is older.

## ghd021

### GHD021 — Relative worktree hook path missing (`warning`)

A linked worktree resolves a relative `core.hooksPath` to a directory that does not exist in that worktree.

## ghd022

### GHD022 — Hook unreadable (`error`)

The current user cannot read the effective hook file, so startup content cannot be validated.

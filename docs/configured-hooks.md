# Configured hooks in Git 2.54+

Git has two hook sources.

## Traditional hook file

```text
<effective hooks directory>/pre-commit
```

The effective directory is normally `$GIT_DIR/hooks`, but `core.hooksPath` can replace it. Git ignores a traditional hook that is not executable on platforms with executable mode bits.

## Named configured hook

Git 2.54 added named hook commands in config:

```ini
[hook "lint"]
    event = pre-commit
    event = pre-push
    command = ~/bin/project-lint --fast

[hook "no-secrets"]
    event = pre-commit
    command = ~/bin/no-secrets
```

For `pre-commit`, Git runs matching configured hooks in config order, followed by the traditional `pre-commit` file when present.

The model creates new failure modes:

- Git 2.53 and older parse the keys as config but do not run them.
- A hook may have events but no effective command.
- A local `enabled=false` can override a global hook.
- A friendly name that equals a known event creates an ambiguity rejected by current Git.
- A relative command is resolved from Git's hook working directory.

## Git 2.55 controls

Git 2.55 adds event-level enable switches and configured-hook parallelism:

```ini
[hook "lint"]
    event = pre-push
    command = ~/bin/lint
    parallel = true

[hook "tests"]
    event = pre-push
    command = ~/bin/test-fast
    parallel = true

[hook]
    jobs = 2

[hook "pre-commit"]
    enabled = false
```

The final block is written in flattened form as `hook.pre-commit.enabled=false`; it disables the entire event. On Git 2.54, event-level and parallel settings are not honored even though the config parser can read them.

Git Hook Doctor reports the difference instead of treating every `hook.*` key as universally supported.

## Version matrix

| Git version | Traditional files | Named configured hooks | Event switch / parallel controls |
|---|---:|---:|---:|
| 2.31–2.53 | yes | no | no |
| 2.54 | yes | yes | no |
| 2.55+ | yes | yes | yes |

Git Hook Doctor supports all rows. On older Git it reports newer configuration as ineffective rather than silently accepting it.

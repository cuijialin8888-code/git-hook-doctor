# Limits and non-goals

Git Hook Doctor makes a narrow promise: explain whether Git can discover and start a hook using evidence visible from the current process.

## What `ready` does not prove

A ready hook may still:

- exit non-zero because its own checks fail;
- use a command that is available in the terminal but absent in an IDE or GUI Git client;
- read unexpected input or assume an unavailable working tree state;
- contain insecure, destructive, or non-portable shell code;
- fail only for a specific Git event argument or stdin payload.

The tool does not execute hooks to test these behaviors because doing so would violate the read-only boundary and could trigger arbitrary repository code.

## Environment limits

- Interpreter checks use the current process PATH plus the bundled shell location of the selected Git for Windows installation.
- IDEs and GUI clients may construct a different PATH.
- Mount options such as POSIX `noexec`, remote filesystem policy, antivirus interception, and application-control policy are not currently probed.
- A malicious or wrapped `git` executable can perform side effects; selecting a trustworthy Git binary is the caller's responsibility.
- Config values injected only into a future command with `git -c` are not visible in an earlier diagnostic run.
- Invocation-time bypasses such as `git commit --no-verify` and framework-specific disable variables are not inferable from repository state.

## Parsing limits

- Plain configured-command targets are resolved. Shell one-liners containing metacharacters are not interpreted.
- Only startup-relevant bytes from hook files are read; the complete script body is not scanned.
- Custom wrapper events are listed when configured, but Git Hook Doctor cannot know when an external wrapper will trigger them.

## Intentional non-goals

- installing, enabling, or repairing hooks;
- running `git hook run` as a probe;
- auditing shell safety or supply-chain trust;
- managing Husky, Lefthook, pre-commit, or another framework;
- scoring repository health;
- uploading reports or telemetry.

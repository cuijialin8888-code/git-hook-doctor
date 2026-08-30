# Contributing

Thanks for improving Git Hook Doctor. The project favors narrow, reproducible diagnostics over broad heuristics.

## Before proposing a rule

A rule should answer all four questions:

1. What exact Git or operating-system behavior prevents the hook from starting?
2. Can the behavior be reproduced in a synthetic repository without executing an untrusted hook?
3. Which platforms and Git versions are affected?
4. What evidence keeps the false-positive rate bounded?

Rules about dangerous shell commands, general repository health, or runtime business logic belong in a different tool.

## Development

```console
python -m venv .venv
python -m pip install -e .
python -m unittest discover -s tests -v
python -m compileall -q src tests
git-hook-doctor check --fail-on error
```

Before opening a pull request, also run:

```console
python -m pip wheel . --no-deps --wheel-dir dist-local
git diff --check
```

## Pull request checklist

- Add or update a synthetic test fixture.
- Test every affected operating system path.
- Keep rule IDs stable; never reuse an existing ID for a different meaning.
- Update `docs/rules.md`, the changelog, and report schemas when behavior changes.
- Preserve the read-only/no-hook-execution boundary.
- Keep the change focused and explain known false negatives.

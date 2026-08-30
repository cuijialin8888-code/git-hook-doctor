# Security policy

## Supported versions

Security fixes are provided for the latest released minor version.

## Reporting a vulnerability

Please use GitHub's private vulnerability reporting for this repository. Do not include secrets, private hook bodies, credentials, or proprietary repository content in a public issue.

Include:

- the Git Hook Doctor version and installation source;
- operating system, Python version, and Git version;
- the smallest synthetic repository that reproduces the issue;
- the expected and observed read-only behavior;
- whether any file outside the requested repository was unexpectedly read.

You should receive an acknowledgement within seven days. A confirmed report will be handled privately until a fix or documented mitigation is available.

## Security boundary

Git Hook Doctor does not execute hook files or configured hook commands. It does execute the selected `git` binary for read-only discovery and config queries. A malicious replacement `git` executable is outside the tool's trust boundary.

Configured-hook arguments, environment assignments, and shell bodies are not emitted in reports. Paths, friendly names, config origins, and executable targets may still be sensitive in private environments; review a report before sharing it.

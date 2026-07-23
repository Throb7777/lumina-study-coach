# Security Policy

## Supported Version

Security fixes currently target the latest public release.

## Reporting a Vulnerability

Please do not disclose a suspected vulnerability in a public issue. Use
GitHub's private vulnerability reporting for this repository. Include:

- The affected version.
- Reproduction steps.
- Expected and observed behavior.
- Any impact on local data, materials, Obsidian files, or external CLI login.

Do not include real credentials, private learning materials, or personal
database files. Acknowledgement is normally provided within seven days.

## Security Boundary

Lumina is a local single-user application that binds to `127.0.0.1`. It is not
designed to be exposed to a LAN or the public internet. External AI CLIs and
downloaded materials remain separate trust boundaries.

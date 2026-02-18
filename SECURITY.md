# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability, please report it responsibly:

1. **Do NOT** open a public issue
2. Email: **security@hauba.dev** (or open a private security advisory on GitHub)
3. Include: description, steps to reproduce, potential impact

We will respond within 48 hours and work on a fix.

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | Yes       |

## Security Features

Hauba includes built-in security protections:

- **Prompt injection detection** — Blocks attempts to override agent instructions via user input
- **Command injection prevention** — Sanitizes shell commands before execution
- **Path traversal protection** — Validates file paths against traversal attacks
- **API key redaction** — Never leaks secrets in logs or error messages
- **Subprocess isolation** — Tool execution runs in isolated subprocesses with timeouts

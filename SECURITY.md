# Security Policy

Codex Reasoning Sentinel is a local guardrail plugin. It can block some risky actions, but it is not a sandbox and should not be treated as a security boundary.

## Supported Versions

Only the latest released version is supported.

## Reporting a Vulnerability

Please open a private security advisory or contact the maintainer through GitHub if you find a vulnerability in hook behavior, command classification, or state handling.

Avoid posting sensitive transcript content in public issues. Redact private paths, prompts, tokens, and repository data before sharing examples.

## Scope

In scope:

- Hook command injection bugs.
- Unsafe parsing behavior.
- Incorrectly allowing obviously risky write actions while a session is suspect.

Out of scope:

- The model producing an incorrect answer.
- Codex hook limitations documented by Codex.
- Local misconfiguration outside this repository.

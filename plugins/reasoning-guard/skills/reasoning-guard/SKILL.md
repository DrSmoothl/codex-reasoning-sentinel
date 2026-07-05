---
name: reasoning-guard
description: Use when the user asks about Reasoning Guard status, clearing the guard, or investigating shallow reasoning-token warnings in Codex.
---

# Reasoning Guard

Reasoning Guard is a local Codex plugin that adds lifecycle hooks around complex or high-stakes work.

When this skill is relevant:

- Treat low `reasoning_output_tokens` values on the `518n - 2` boundary, such as `516`, `1034`, or `1552`, as a warning sign rather than proof of correctness.
- If Reasoning Guard says a previous turn is suspect, redo the reasoning from first principles before relying on the prior answer.
- For complex refactors, migrations, math, proofs, debugging, security, or production changes, verify with an independent check before editing files or giving a final answer.
- If the user intentionally wants to clear the local guard state, they can send `reasoning-guard: allow` or `reasoning-guard: clear`.

The plugin cannot force hidden model reasoning. It can detect suspicious telemetry, request one more pass through a Stop hook, inject slow-path context, and block risky write tools while the previous turn remains suspect.

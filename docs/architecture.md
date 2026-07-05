# Architecture

Codex Reasoning Sentinel is packaged as a Codex local marketplace containing the `reasoning-guard` plugin.

## Flow

1. `UserPromptSubmit` marks complex prompts and injects slow-path context.
2. `Stop` and `SubagentStop` inspect the latest transcript token usage.
3. If a suspicious condition is found, the hook returns `decision: block` with a continuation prompt.
4. If a suspect state remains active, `PreToolUse` and `PermissionRequest` block risky write-like operations.
5. A later healthy Stop event or an explicit user bypass clears the suspect state.

## Suspicious Conditions

The default configuration flags:

- low `518n - 2` boundaries from `516` through `1999`
- complex prompts that complete below `REASONING_GUARD_MIN_COMPLEX_REASONING`

The low-boundary cap intentionally avoids treating all `518n - 2` values as bad. Long reasoning values can also fall on that arithmetic boundary.

## State

State is stored per Codex `session_id` in `PLUGIN_DATA`, or in a temporary directory when running outside a plugin install. The state has a configurable TTL.

## Safety Model

This project is a workflow guardrail. It is not a complete enforcement layer. Codex hook coverage can change, transcript fields are not a stable API, and tools outside the supported hook surfaces may not be intercepted.

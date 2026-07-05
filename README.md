# Codex Reasoning Sentinel

[English](README.md) | [简体中文](README.zh-CN.md)

Codex Reasoning Sentinel is an unofficial local Codex plugin that adds guardrails around suspiciously shallow reasoning turns. It watches Codex hook telemetry, asks for one extra verification pass when a turn looks suspect, and blocks risky write actions until the suspect state is cleared or repaired.

The first bundled plugin is **Reasoning Guard**.

## Why

For complex refactors, migrations, debugging sessions, and math-heavy work, a short or shortcut-like answer can be worse than no answer: it may confidently edit files before the plan has been properly checked.

Reasoning Guard does not claim to prove hidden reasoning quality. Instead, it turns a few practical warning signs into a visible, interruptible workflow:

- low `reasoning_output_tokens` on suspicious `518n - 2` boundaries such as `516`, `1034`, or `1552`
- complex prompts that complete below a configurable reasoning-token threshold
- risky write tools being invoked after a suspect turn

## Features

- Adds slow-path context for complex or high-stakes prompts.
- Detects suspicious low reasoning-token boundaries from Codex transcript telemetry.
- Uses `Stop` and `SubagentStop` hooks to request one automatic verification continuation.
- Marks the session suspect when a shallow or boundary turn persists.
- Blocks risky tools while suspect, including `apply_patch`, write-like MCP tools, destructive shell commands, and mutating git commands.
- Allows read-only inspection and common test commands so the agent can verify safely.
- Provides an explicit bypass phrase for intentional overrides.

## Install

Clone the repository:

```bash
git clone https://github.com/DrSmoothl/codex-reasoning-sentinel.git
cd codex-reasoning-sentinel
```

Register the local marketplace and install the plugin:

```bash
codex plugin marketplace add "$PWD"
codex plugin add reasoning-guard@codex-reasoning-sentinel
```

Then start a new Codex thread. Codex will ask you to review and trust the bundled hooks before they run.

## Usage

Once installed, Reasoning Guard runs through Codex lifecycle hooks. You do not need to call it directly.

If a turn is considered suspect, the Stop hook returns a continuation prompt so Codex performs one more verification pass before finalizing. If the session remains suspect, write-like tools are blocked until the reasoning is repaired or the guard is explicitly cleared.

To clear the current session state, send either:

```text
reasoning-guard: allow
reasoning-guard: clear
```

## Configuration

The hook script reads these optional environment variables:

| Variable | Default | Meaning |
| --- | --- | --- |
| `REASONING_GUARD_MIN_COMPLEX_REASONING` | `2000` | Minimum reasoning tokens expected after a complex prompt. |
| `REASONING_GUARD_BOUNDARY_MAX` | `1999` | Maximum low-boundary value to flag. Raise it to flag higher `518n - 2` values. |
| `REASONING_GUARD_ENFORCE_COMPLEX_MIN` | `1` | Set to `0` to only enforce boundary detection. |
| `REASONING_GUARD_TOOL_POLICY` | `block-writes` | Set to `block-all-shell` for a stricter suspect-state shell policy. |
| `REASONING_GUARD_STATE_TTL_SECONDS` | `43200` | Time-to-live for suspect state. |
| `REASONING_GUARD_DATA` | unset | Optional writable state directory, useful for local testing. |

## Project Layout

```text
.
├── marketplace.json
├── plugins/
│   └── reasoning-guard/
│       ├── .codex-plugin/plugin.json
│       ├── hooks/hooks.json
│       ├── scripts/reasoning_guard.py
│       ├── skills/reasoning-guard/SKILL.md
│       └── tests/fixtures/
└── docs/
```

## Development

Validate the Python hook:

```bash
python3 -m py_compile plugins/reasoning-guard/scripts/reasoning_guard.py
```

Run a fixture parse:

```bash
python3 plugins/reasoning-guard/scripts/reasoning_guard.py analyze \
  plugins/reasoning-guard/tests/fixtures/suspect-516.jsonl
```

Validate the plugin manifest with the Codex plugin validator when available:

```bash
uv run --with pyyaml python /path/to/validate_plugin.py plugins/reasoning-guard
```

## Limitations

- This plugin cannot force a hidden reasoning-token count.
- It cannot prove that a model reasoned correctly.
- It cannot intercept every possible side effect.
- It depends on Codex transcript telemetry, which is useful for hooks but not a stable long-term interface.
- It is an unofficial community project and is not affiliated with OpenAI.

## License

MIT. See [LICENSE](LICENSE).

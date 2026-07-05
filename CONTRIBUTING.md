# Contributing

Thanks for taking an interest in Codex Reasoning Sentinel.

## Development Setup

This project intentionally avoids runtime dependencies. The main implementation is a Python standard-library hook script.

Validate the hook script:

```bash
python3 -m py_compile plugins/reasoning-guard/scripts/reasoning_guard.py
```

Run fixture analysis:

```bash
python3 plugins/reasoning-guard/scripts/reasoning_guard.py analyze \
  plugins/reasoning-guard/tests/fixtures/suspect-516.jsonl
```

## Pull Request Guidelines

- Keep hook behavior conservative and easy to explain.
- Prefer transparent warnings and continuation prompts over silent automation.
- Add or update fixtures when changing transcript parsing.
- Document any new environment variables in both README files.

## Reporting Issues

Please include:

- Codex surface: CLI, desktop app, IDE, or other.
- Model and reasoning effort if visible.
- The relevant `reasoning_output_tokens` value.
- Whether the hook produced a continuation, warning, or tool block.
- A minimal transcript fixture when possible, with private content removed.

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any


DEFAULT_MODEL = "gpt-5.5"
DEFAULT_INSTRUCTIONS_CONFIG_VALUE = "~/.codex/model-instructions.md"
INTERMEDIARY_MARKER = "\n## Intermediary updates"


def codex_home_default() -> Path:
    configured = os.environ.get("CODEX_HOME")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".codex"


def toml_quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def load_base_instructions(models_cache_path: Path, model: str) -> str:
    cache = json.loads(models_cache_path.read_text(encoding="utf-8"))
    models = cache.get("models")
    if not isinstance(models, list):
        raise ValueError(f"{models_cache_path} does not contain a models list")
    for candidate in models:
        if isinstance(candidate, dict) and candidate.get("slug") == model:
            instructions = candidate.get("base_instructions")
            if isinstance(instructions, str):
                return instructions
            raise ValueError(f"{model} is missing base_instructions in {models_cache_path}")
    raise ValueError(f"{model} was not found in {models_cache_path}")


def strip_intermediary_updates(instructions: str) -> tuple[str, bool]:
    marker_index = instructions.rfind(INTERMEDIARY_MARKER)
    if marker_index < 0:
        return instructions if instructions.endswith("\n") else instructions + "\n", False
    stripped = instructions[:marker_index].rstrip() + "\n"
    return stripped, True


def split_top_level_config(config_text: str) -> tuple[list[str], list[str]]:
    lines = config_text.splitlines()
    for index, line in enumerate(lines):
        if line.lstrip().startswith("["):
            return lines[:index], lines[index:]
    return lines, []


def newline_for(text: str) -> str:
    return "\r\n" if "\r\n" in text else "\n"


def update_top_level_config(config_text: str, updates: dict[str, str]) -> str:
    newline = newline_for(config_text)
    preamble, rest = split_top_level_config(config_text)
    rendered = {key: f"{key} = {toml_quote(value)}" for key, value in updates.items()}
    seen: set[str] = set()
    next_preamble: list[str] = []

    for line in preamble:
        matched_key = None
        for key in updates:
            if re.match(rf"^\s*{re.escape(key)}\s*=", line):
                matched_key = key
                break
        if matched_key is None:
            next_preamble.append(line)
            continue
        if matched_key not in seen:
            next_preamble.append(rendered[matched_key])
            seen.add(matched_key)

    missing = [key for key in updates if key not in seen]
    if missing:
        trailing_blank_count = 0
        while next_preamble and next_preamble[-1].strip() == "":
            next_preamble.pop()
            trailing_blank_count += 1
        for key in missing:
            next_preamble.append(rendered[key])
        if rest:
            trailing_blank_count = max(trailing_blank_count, 1)
        next_preamble.extend("" for _ in range(trailing_blank_count))

    next_lines = next_preamble + rest
    return newline.join(next_lines).rstrip() + newline


def apply_hotfix(
    codex_home: Path,
    *,
    model: str = DEFAULT_MODEL,
    instructions_file: Path | None = None,
    instructions_config_value: str = DEFAULT_INSTRUCTIONS_CONFIG_VALUE,
    check: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    codex_home = codex_home.expanduser()
    models_cache_path = codex_home / "models_cache.json"
    config_path = codex_home / "config.toml"
    instructions_path = instructions_file.expanduser() if instructions_file else codex_home / "model-instructions.md"

    base_instructions = load_base_instructions(models_cache_path, model)
    stripped_instructions, removed_marker = strip_intermediary_updates(base_instructions)

    current_instructions = ""
    if instructions_path.exists():
        current_instructions = instructions_path.read_text(encoding="utf-8")
    instructions_change = current_instructions != stripped_instructions

    config_text = ""
    if config_path.exists():
        config_text = config_path.read_text(encoding="utf-8")
    next_config = update_top_level_config(
        config_text,
        {
            "model": model,
            "model_instructions_file": instructions_config_value,
        },
    )
    config_change = config_text != next_config

    if not check and not dry_run:
        instructions_path.parent.mkdir(parents=True, exist_ok=True)
        if instructions_change:
            instructions_path.write_text(stripped_instructions, encoding="utf-8", newline="\n")
        if config_change:
            config_path.write_text(next_config, encoding="utf-8", newline="\n")

    return {
        "model": model,
        "codex_home": str(codex_home),
        "models_cache_path": str(models_cache_path),
        "config_path": str(config_path),
        "instructions_path": str(instructions_path),
        "instructions_config_value": instructions_config_value,
        "source_had_intermediary_updates": removed_marker,
        "instructions_change": instructions_change,
        "config_change": config_change,
        "check": check,
        "dry_run": dry_run,
    }


def print_result(result: dict[str, Any]) -> None:
    action = "check" if result["check"] else "dry run" if result["dry_run"] else "apply"
    print(f"Codex {result['model']} prompt hotfix {action}:")
    print(f"- source had Intermediary updates: {result['source_had_intermediary_updates']}")
    print(f"- instructions file: {result['instructions_path']}")
    print(f"- instructions needs update: {result['instructions_change']}")
    print(f"- config file: {result['config_path']}")
    print(f"- config needs update: {result['config_change']}")
    print(f"- locked model: {result['model']}")
    print(f"- config instructions value: {result['instructions_config_value']}")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Apply the Codex 5.5 prompt hotfix by writing base_instructions without "
            "the final '## Intermediary updates' block and locking config.toml to gpt-5.5."
        )
    )
    parser.add_argument("--codex-home", type=Path, default=codex_home_default())
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--instructions-file", type=Path)
    parser.add_argument("--instructions-config-value", default=DEFAULT_INSTRUCTIONS_CONFIG_VALUE)
    parser.add_argument("--check", action="store_true", help="verify only; exit 1 if updates are needed")
    parser.add_argument("--dry-run", action="store_true", help="show what would change without writing")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    try:
        result = apply_hotfix(
            args.codex_home,
            model=args.model,
            instructions_file=args.instructions_file,
            instructions_config_value=args.instructions_config_value,
            check=args.check,
            dry_run=args.dry_run,
        )
    except Exception as exc:
        print(f"Codex prompt hotfix failed: {exc}", file=sys.stderr)
        return 2

    print_result(result)
    if args.check and (result["instructions_change"] or result["config_change"]):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

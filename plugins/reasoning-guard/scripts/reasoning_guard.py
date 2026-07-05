#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any


PLUGIN_NAME = "Reasoning Guard"
BOUNDARY_STEP = int(os.environ.get("REASONING_GUARD_BOUNDARY_STEP", "518"))
BOUNDARY_OFFSET = int(os.environ.get("REASONING_GUARD_BOUNDARY_OFFSET", "-2"))
BOUNDARY_MIN = int(os.environ.get("REASONING_GUARD_BOUNDARY_MIN", "516"))
BOUNDARY_MAX = int(os.environ.get("REASONING_GUARD_BOUNDARY_MAX", "1999"))
MIN_COMPLEX_REASONING = int(os.environ.get("REASONING_GUARD_MIN_COMPLEX_REASONING", "2000"))
STATE_TTL_SECONDS = int(os.environ.get("REASONING_GUARD_STATE_TTL_SECONDS", "43200"))
ENFORCE_COMPLEX_MIN = os.environ.get("REASONING_GUARD_ENFORCE_COMPLEX_MIN", "1") not in {"0", "false", "False"}
TOOL_POLICY = os.environ.get("REASONING_GUARD_TOOL_POLICY", "block-writes")


COMPLEX_RE = re.compile(
    r"(?i)("
    r"complex|important|refactor|migration|architecture|design|proof|prove|"
    r"math|mathematical|bug|debug|security|production|release|data loss|"
    r"xhigh|2000 reasoning|2000 token|"
    r"复杂|重要|重构|迁移|架构|证明|数学|线上|生产|安全|必须|主动思考"
    r")"
)

BYPASS_RE = re.compile(
    r"(?i)(/reasoning-guard\s+allow|reasoning-guard:\s*allow|\[reasoning-guard\s+allow\]|"
    r"/reasoning-guard\s+clear|reasoning-guard:\s*clear|\[reasoning-guard\s+clear\])"
)

READ_ONLY_OR_VERIFYING_SHELL_RE = re.compile(
    r"(?is)^\s*("
    r"pwd|ls\b|find\b|rg\b|grep\b|sed\s+-n\b|cat\b|head\b|tail\b|wc\b|"
    r"git\s+(status|diff|show|log|rev-parse|branch|remote|ls-files)\b|"
    r"pytest\b|python3?\s+-m\s+pytest\b|npm\s+(test|run\s+test)\b|"
    r"pnpm\s+(test|run\s+test)\b|yarn\s+(test|run\s+test)\b|"
    r"cargo\s+test\b|go\s+test\b|make\s+test\b|"
    r"\./gradlew\s+.*test\b|gradle\s+.*test\b"
    r")"
)

RISKY_SHELL_RE = re.compile(
    r"(?is)("
    r"(^|\s)(rm|mv|cp|chmod|chown|dd|mkfs|killall)\b|"
    r"git\s+(commit|push|reset|checkout|clean|rebase|merge|tag)\b|"
    r"sed\s+-i\b|perl\s+-pi\b|"
    r">\s*[^&]|>>|tee\s+|cat\s*>|"
    r"apply_patch\b|"
    r"python3?\b.*\b(open|write_text|unlink|rmtree|remove|rename)\b"
    r")"
)

RISKY_MCP_RE = re.compile(r"(?i)(write|edit|delete|remove|create|update|patch|move|rename|commit|push)")


def read_stdin_json() -> dict[str, Any]:
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        return {"hook_event_name": "Unknown", "_parse_error": str(exc), "_raw": raw[:1000]}
    return value if isinstance(value, dict) else {"_input": value}


def emit(payload: dict[str, Any] | None = None) -> None:
    if payload:
        print(json.dumps(payload, ensure_ascii=False))


def plugin_data_dir() -> Path:
    configured = (
        os.environ.get("REASONING_GUARD_DATA")
        or os.environ.get("PLUGIN_DATA")
        or os.environ.get("CLAUDE_PLUGIN_DATA")
    )
    if configured:
        path = Path(configured).expanduser()
    else:
        path = Path(os.environ.get("TMPDIR", "/tmp")) / "reasoning-guard"
    path.mkdir(parents=True, exist_ok=True)
    return path


def session_key(payload: dict[str, Any]) -> str:
    raw = str(payload.get("session_id") or "default")
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", raw)[:120] or "default"


def state_path(payload: dict[str, Any]) -> Path:
    return plugin_data_dir() / f"{session_key(payload)}.json"


def load_state(payload: dict[str, Any]) -> dict[str, Any]:
    path = state_path(payload)
    if not path.exists():
        return {}
    try:
        state = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(state, dict):
        return {}
    ts = float(state.get("timestamp") or 0)
    if ts and time.time() - ts > STATE_TTL_SECONDS:
        clear_state(payload)
        return {}
    return state


def save_state(payload: dict[str, Any], state: dict[str, Any]) -> None:
    state["timestamp"] = time.time()
    state_path(payload).write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n")


def clear_state(payload: dict[str, Any]) -> None:
    try:
        state_path(payload).unlink()
    except FileNotFoundError:
        pass


def stable_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]


def iter_dicts(value: Any):
    if isinstance(value, dict):
        yield value
        for nested in value.values():
            yield from iter_dicts(nested)
    elif isinstance(value, list):
        for item in value:
            yield from iter_dicts(item)


def int_value(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str) and re.fullmatch(r"-?\d+", value.strip()):
        return int(value.strip())
    return None


def usage_from_record(record: dict[str, Any]) -> dict[str, Any] | None:
    best: dict[str, Any] | None = None
    for item in iter_dicts(record):
        reasoning = int_value(item.get("reasoning_output_tokens"))
        if reasoning is None:
            details = item.get("output_tokens_details")
            if isinstance(details, dict):
                reasoning = int_value(details.get("reasoning_tokens"))
        if reasoning is None:
            reasoning = int_value(item.get("reasoning_tokens"))
        if reasoning is None:
            continue

        candidate = {
            "reasoning_output_tokens": reasoning,
            "input_tokens": int_value(item.get("input_tokens")),
            "cached_input_tokens": int_value(item.get("cached_input_tokens")),
            "output_tokens": int_value(item.get("output_tokens")),
            "total_tokens": int_value(item.get("total_tokens")),
        }
        best = {k: v for k, v in candidate.items() if v is not None}
    return best


def find_value(record: dict[str, Any], keys: set[str]) -> Any:
    for item in iter_dicts(record):
        for key in keys:
            if key in item:
                return item[key]
    return None


def analyze_transcript(path_text: str | None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "transcript_path": path_text,
        "exists": False,
        "latest_usage": None,
        "model": None,
        "reasoning_effort": None,
        "lines_read": 0,
        "error": None,
    }
    if not path_text:
        result["error"] = "missing transcript_path"
        return result

    path = Path(path_text).expanduser()
    if not path.exists():
        result["error"] = "transcript_path does not exist"
        return result

    result["exists"] = True
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line_no, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                result["lines_read"] = line_no
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(record, dict):
                    continue
                usage = usage_from_record(record)
                if usage is not None:
                    usage["line"] = line_no
                    result["latest_usage"] = usage
                if result["model"] is None:
                    model = find_value(record, {"model"})
                    if isinstance(model, str):
                        result["model"] = model
                if result["reasoning_effort"] is None:
                    effort = find_value(record, {"model_reasoning_effort", "reasoning_effort"})
                    if isinstance(effort, str):
                        result["reasoning_effort"] = effort
    except OSError as exc:
        result["error"] = str(exc)
    return result


def is_boundary(reasoning: int) -> bool:
    return (
        BOUNDARY_MIN <= reasoning <= BOUNDARY_MAX
        and (reasoning - BOUNDARY_OFFSET) % BOUNDARY_STEP == 0
    )


def is_complex_prompt(prompt: str) -> bool:
    stripped = prompt.strip()
    return len(stripped) >= 900 or COMPLEX_RE.search(stripped) is not None


def slow_path_context() -> str:
    return (
        "Reasoning Guard is active. This prompt appears complex or high stakes. "
        "Use the slow path: inspect the relevant facts, avoid a first-plausible shortcut, "
        "verify with an independent check before finalizing, and do not edit files until "
        "the plan or diagnosis has survived that check. For math, recompute by a second method. "
        "For refactors, read the affected code and run focused verification."
    )


def continuation_prompt(reasons: list[str], analysis: dict[str, Any]) -> str:
    usage = analysis.get("latest_usage") or {}
    reasoning = usage.get("reasoning_output_tokens")
    model = analysis.get("model") or "unknown model"
    reason_text = "; ".join(reasons)
    return (
        f"{PLUGIN_NAME} detected a suspect reasoning turn on {model}: {reason_text}. "
        f"The latest reasoning_output_tokens value is {reasoning}. "
        "Continue now from scratch before finalizing. Re-check the conclusion independently, "
        "call out any previous mistake, and only then give the final answer or proceed with tools. "
        "Do not treat the previous answer as verified."
    )


def suspicious_reasons(payload: dict[str, Any], analysis: dict[str, Any]) -> list[str]:
    usage = analysis.get("latest_usage") or {}
    reasoning = usage.get("reasoning_output_tokens")
    if not isinstance(reasoning, int):
        return []

    state = load_state(payload)
    reasons: list[str] = []
    if is_boundary(reasoning):
        reasons.append(
            f"reasoning_output_tokens={reasoning} is on the low 518n-2 boundary "
            f"range [{BOUNDARY_MIN}, {BOUNDARY_MAX}]"
        )

    complex_pending = bool(state.get("last_prompt_complex"))
    if ENFORCE_COMPLEX_MIN and complex_pending and reasoning < MIN_COMPLEX_REASONING:
        reasons.append(
            f"complex prompt expected at least {MIN_COMPLEX_REASONING} reasoning tokens, got {reasoning}"
        )
    return reasons


def handle_session_start(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": (
                "Reasoning Guard is enabled. If a complex turn ends with suspiciously shallow "
                "reasoning telemetry, hooks may request one more verification pass and may block "
                "risky write tools until the turn is repaired."
            ),
        }
    }


def handle_user_prompt(payload: dict[str, Any]) -> dict[str, Any]:
    prompt = str(payload.get("prompt") or "")
    if BYPASS_RE.search(prompt):
        clear_state(payload)
        return {
            "systemMessage": "Reasoning Guard state cleared for this session.",
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": "Reasoning Guard bypass was explicitly requested by the user.",
            },
        }

    state = load_state(payload)
    complex_prompt = is_complex_prompt(prompt)
    state["last_prompt_complex"] = complex_prompt
    state["last_prompt_hash"] = stable_hash(prompt)
    state["last_prompt_turn_id"] = payload.get("turn_id")
    save_state(payload, state)

    contexts: list[str] = []
    if state.get("suspect"):
        contexts.append(
            "Previous assistant turn was marked suspect by Reasoning Guard. Treat the prior answer "
            "as unverified, re-check from first principles, and avoid file edits until repaired."
        )
    if complex_prompt:
        contexts.append(slow_path_context())

    if not contexts:
        return {}
    return {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": "\n\n".join(contexts),
        }
    }


def handle_subagent_start(payload: dict[str, Any]) -> dict[str, Any]:
    state = load_state(payload)
    if not state.get("last_prompt_complex"):
        return {}
    return {
        "hookSpecificOutput": {
            "hookEventName": "SubagentStart",
            "additionalContext": slow_path_context(),
        }
    }


def handle_stop_like(payload: dict[str, Any], event_name: str) -> dict[str, Any]:
    path_key = "agent_transcript_path" if event_name == "SubagentStop" else "transcript_path"
    analysis = analyze_transcript(payload.get(path_key) or payload.get("transcript_path"))
    if payload.get("model") and not analysis.get("model"):
        analysis["model"] = payload.get("model")
    reasons = suspicious_reasons(payload, analysis)

    if not reasons:
        state = load_state(payload)
        if state.get("suspect"):
            clear_state(payload)
        return {}

    state = load_state(payload)
    state.update(
        {
            "suspect": True,
            "suspect_event": event_name,
            "suspect_reasons": reasons,
            "suspect_analysis": analysis,
            "suspect_turn_id": payload.get("turn_id"),
        }
    )
    save_state(payload, state)

    if payload.get("stop_hook_active"):
        return {
            "systemMessage": (
                f"{PLUGIN_NAME}: suspect reasoning persisted after one continuation; "
                "state is marked suspect and risky write tools may be blocked."
            )
        }

    return {
        "decision": "block",
        "reason": continuation_prompt(reasons, analysis),
    }


def tool_text(payload: dict[str, Any]) -> str:
    tool_input = payload.get("tool_input")
    if isinstance(tool_input, dict):
        command = tool_input.get("command")
        if isinstance(command, str):
            return command
        return json.dumps(tool_input, ensure_ascii=False, sort_keys=True)
    if isinstance(tool_input, str):
        return tool_input
    return ""


def is_risky_tool(payload: dict[str, Any]) -> tuple[bool, str]:
    tool_name = str(payload.get("tool_name") or "")
    command = tool_text(payload)
    lower_name = tool_name.lower()

    if lower_name in {"apply_patch", "edit", "write"}:
        return True, f"{tool_name} edits files"
    if tool_name.startswith("mcp__") and RISKY_MCP_RE.search(tool_name):
        return True, f"{tool_name} looks write-capable"
    if lower_name == "bash":
        if READ_ONLY_OR_VERIFYING_SHELL_RE.search(command) and not RISKY_SHELL_RE.search(command):
            return False, "read-only or verification shell command"
        if RISKY_SHELL_RE.search(command):
            return True, "shell command appears to mutate files, git state, or system state"
        if TOOL_POLICY == "block-all-shell":
            return True, "shell commands are blocked while a suspect turn is active"
    return False, "not classified as risky"


def suspect_tool_message(state: dict[str, Any], payload: dict[str, Any], reason: str) -> str:
    usage = ((state.get("suspect_analysis") or {}).get("latest_usage") or {})
    reasoning = usage.get("reasoning_output_tokens", "unknown")
    reasons = "; ".join(state.get("suspect_reasons") or ["previous turn marked suspect"])
    return (
        f"{PLUGIN_NAME} blocked this tool because the previous turn is still suspect "
        f"({reasons}; reasoning_output_tokens={reasoning}). Tool risk: {reason}. "
        "Ask the model to redo/verify the reasoning first, or send 'reasoning-guard: allow' "
        "if you intentionally want to clear the guard state."
    )


def handle_pre_tool(payload: dict[str, Any]) -> dict[str, Any]:
    state = load_state(payload)
    if not state.get("suspect"):
        return {}
    risky, reason = is_risky_tool(payload)
    if not risky:
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": (
                    f"{PLUGIN_NAME}: previous turn is marked suspect. This tool was allowed "
                    "because it looks read-only or verification-oriented."
                ),
            }
        }
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": suspect_tool_message(state, payload, reason),
        }
    }


def handle_permission_request(payload: dict[str, Any]) -> dict[str, Any]:
    state = load_state(payload)
    if not state.get("suspect"):
        return {}
    risky, reason = is_risky_tool(payload)
    if not risky:
        return {}
    return {
        "hookSpecificOutput": {
            "hookEventName": "PermissionRequest",
            "decision": {
                "behavior": "deny",
                "message": suspect_tool_message(state, payload, reason),
            },
        }
    }


def main() -> int:
    if len(sys.argv) >= 3 and sys.argv[1] == "analyze":
        print(json.dumps(analyze_transcript(sys.argv[2]), indent=2, ensure_ascii=False))
        return 0

    payload = read_stdin_json()
    event = str(payload.get("hook_event_name") or payload.get("hookEventName") or "")

    try:
        if event == "SessionStart":
            emit(handle_session_start(payload))
        elif event == "UserPromptSubmit":
            emit(handle_user_prompt(payload))
        elif event == "SubagentStart":
            emit(handle_subagent_start(payload))
        elif event == "Stop":
            emit(handle_stop_like(payload, "Stop"))
        elif event == "SubagentStop":
            emit(handle_stop_like(payload, "SubagentStop"))
        elif event == "PreToolUse":
            emit(handle_pre_tool(payload))
        elif event == "PermissionRequest":
            emit(handle_permission_request(payload))
        else:
            emit({})
    except Exception as exc:
        emit({"systemMessage": f"{PLUGIN_NAME} hook failed closed-soft: {exc}"})
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

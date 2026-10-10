from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

try:
    import anthropic
except ModuleNotFoundError:  # pragma: no cover - exercised only when dependency is absent.
    anthropic = None

try:
    from dotenv import dotenv_values
except ModuleNotFoundError:  # pragma: no cover - tiny fallback for undeclared local envs.
    def dotenv_values(path: Path) -> dict[str, str]:
        if not path.exists():
            return {}
        values: dict[str, str] = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line or line.lstrip().startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip("\"'")
        return values
from pydantic import ValidationError

from policy.prompts import build_retry_message, build_system_prompt, build_user_message
from shared.models import CompileResult, Rules
from shared.store import load_default_rules

_DOTENV_PATH = Path(__file__).resolve().parent.parent / ".env"
_DEFAULT_MODEL = "claude-haiku-5-5"
_TOOL_NAME = "emit_rules"


def compile_policy(text: str) -> CompileResult:
    """Never raises. On any failure returns default rules with fallback metadata."""
    try:
        return _compile(text)
    except Exception as exc:
        return _fallback(text, f"unexpected error: {_exc_text(exc)}")


def _compile(text: str) -> CompileResult:
    guard_error = _input_guard(text)
    if guard_error:
        return _fallback(text, guard_error)

    api_key = _load_api_key()
    if not api_key:
        return _fallback(text, "ANTHROPIC_API_KEY is not set")

    client = _make_client(api_key)
    defaults = _safe_default_rules()
    system_prompt = build_system_prompt(defaults)
    first_message = build_user_message(text)

    try:
        rules, unmapped, ambiguities = _attempt_compile(client, text, system_prompt, first_message)
    except _InvalidOutput as exc:
        try:
            retry_message = build_retry_message(text, str(exc))
            rules, unmapped, ambiguities = _attempt_compile(client, text, system_prompt, retry_message)
        except _InvalidOutput as retry_exc:
            return _fallback(text, f"model output failed validation after retry: {retry_exc}")
        except _api_exceptions() as api_exc:
            return _fallback(text, _api_error(api_exc, api_key))
    except _api_exceptions() as api_exc:
        return _fallback(text, _api_error(api_exc, api_key))

    return CompileResult(
        rules=rules,
        unmapped_clauses=unmapped,
        ambiguities=ambiguities,
        used_fallback=False,
        error=None,
    )


def _make_client(api_key: str) -> Any:
    if anthropic is None:
        raise RuntimeError("anthropic package is not installed")
    return anthropic.Anthropic(api_key=api_key, max_retries=0, timeout=20.0)


def _attempt_compile(
    client: Any, text: str, system_prompt: str, user_message: str
) -> tuple[Rules, list[str], list[str]]:
    payload = _call_model(client, text, system_prompt, user_message)
    return _validate_payload(payload, text)


def _input_guard(text: Any) -> str | None:
    if not isinstance(text, str):
        return "policy text must be a string"
    if not text.strip():
        return "policy text is empty"
    if len(text) > 20_000:
        return "policy text is too long"
    return None


def _load_api_key() -> str | None:
    key = os.getenv("ANTHROPIC_API_KEY")
    if key and key.strip():
        return key.strip()
    values = dotenv_values(_DOTENV_PATH)
    key = values.get("ANTHROPIC_API_KEY")
    if key and key.strip():
        return key.strip()
    return None


def _call_model(client: Any, text: str, system_prompt: str, user_message: str) -> dict[str, Any]:
    response = client.messages.create(
        model=os.getenv("ANTHROPIC_MODEL") or _DEFAULT_MODEL,
        max_tokens=1024,
        system=system_prompt,
        tools=[_emit_rules_tool()],
        tool_choice={"type": "tool", "name": _TOOL_NAME},
        messages=[{"role": "user", "content": user_message}],
    )
    if getattr(response, "stop_reason", None) == "max_tokens":
        raise _InvalidOutput("model output was truncated at max_tokens")
    for block in getattr(response, "content", []) or []:
        if getattr(block, "type", None) == "tool_use" and getattr(block, "name", None) == _TOOL_NAME:
            payload = getattr(block, "input", None)
            if isinstance(payload, dict):
                return payload
            raise _InvalidOutput("emit_rules input was not an object")
    raise _InvalidOutput("missing emit_rules tool_use block")


def _emit_rules_tool() -> dict[str, Any]:
    return {
        "name": _TOOL_NAME,
        "description": "Emit validated hostel allocation rules and audit clause lists.",
        "input_schema": {
            "type": "object",
            "properties": {
                "rules": Rules.model_json_schema(),
                "unmapped_clauses": {"type": "array", "items": {"type": "string"}},
                "ambiguities": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["rules", "unmapped_clauses", "ambiguities"],
        },
    }


def _validate_payload(payload: dict[str, Any], text: str) -> tuple[Rules, list[str], list[str]]:
    rules_dict = payload.get("rules")
    if not isinstance(rules_dict, dict):
        raise _InvalidOutput("rules must be an object")
    unmapped = _coerce_clause_list(payload.get("unmapped_clauses", []), "unmapped_clauses", text)
    ambiguities = _coerce_clause_list(payload.get("ambiguities", []), "ambiguities", text)
    defaults = _safe_default_rules()
    rules_dict = _drop_null_values(rules_dict)
    merged = {**defaults.model_dump(mode="json"), **rules_dict}
    try:
        rules = Rules.model_validate(merged)
    except ValidationError as exc:
        raise _InvalidOutput(str(exc)) from exc
    rules = rules.model_copy(update={"source_text": text})
    rules = _naive_deadline(rules)
    return rules, unmapped, ambiguities


def _naive_deadline(rules: Rules) -> Rules:
    """Drop tzinfo from a timezone-aware retention_deadline, keeping the wall-clock time as written.

    The fixtures and the allocator use naive datetimes; an aware deadline would make
    engine.allocate raise on comparison. The time is NOT shifted between zones.
    """
    deadline = rules.retention_deadline
    if deadline is not None and deadline.tzinfo is not None:
        return rules.model_copy(update={"retention_deadline": deadline.replace(tzinfo=None)})
    return rules


def _coerce_clause_list(value: Any, label: str, text: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise _InvalidOutput(f"{label} must be a list of strings")
    cleaned: list[str] = []
    seen: set[str] = set()
    normalised_text = _normalise(text)
    for item in value:
        clause = item
        if _normalise(item) not in normalised_text or item not in text:
            snapped = _snap_to_source(item, text)
            if snapped is None:
                raise _InvalidOutput(f"{label} entry was not copied verbatim: {item}")
            clause = snapped
        key = _normalise(clause)
        if key not in seen:
            seen.add(key)
            cleaned.append(clause)
    return cleaned


def _snap_to_source(clause: str, text: str) -> str | None:
    clause_tokens = _tokens(clause)
    if not clause_tokens:
        return None
    best_sentence = None
    best_score = 0.0
    for sentence in _sentences(text):
        sentence_tokens = _tokens(sentence)
        if not sentence_tokens:
            continue
        score = len(clause_tokens & sentence_tokens) / len(clause_tokens | sentence_tokens)
        if score > best_score:
            best_sentence = sentence
            best_score = score
    return best_sentence if best_sentence is not None and best_score >= 0.6 else None


def _sentences(text: str) -> list[str]:
    pieces = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [piece.strip() for piece in pieces if piece.strip()]


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[A-Za-z0-9']+", text.lower()))


def _normalise(text: str) -> str:
    return " ".join(text.split())


def _drop_null_values(rules_dict: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in rules_dict.items() if value is not None}


def _safe_default_rules() -> Rules:
    try:
        return load_default_rules()
    except Exception:
        return Rules()


def _fallback(text: Any, error: str) -> CompileResult:
    source_text = text if isinstance(text, str) else ""
    try:
        rules = _safe_default_rules().model_copy(update={"source_text": source_text})
        return CompileResult(
            rules=rules,
            unmapped_clauses=[],
            ambiguities=[],
            used_fallback=True,
            error=_safe_error(error or "unknown error"),
        )
    except Exception as exc:
        try:
            return CompileResult(
                rules=Rules(source_text=source_text),
                unmapped_clauses=[],
                ambiguities=[],
                used_fallback=True,
                error=_safe_error(f"fallback failed: {_exc_text(exc)}"),
            )
        except Exception:
            return CompileResult(
                rules=Rules(),
                used_fallback=True,
                error="fallback failed",
            )


def _exc_text(exc: BaseException) -> str:
    """Format `Type: message` without ever raising, even if the exception's __str__ does."""
    try:
        name = type(exc).__name__
    except Exception:
        name = "Exception"
    try:
        return f"{name}: {exc}"
    except Exception:
        return name


def _redact(message: str, api_key: str | None) -> str:
    if api_key:
        message = message.replace(api_key, "***")
    return message


def _safe_error(message: str) -> str:
    """Redact the resolved API key, then truncate, so no error string can carry the key."""
    try:
        api_key = _load_api_key()
    except Exception:
        api_key = None
    return _redact(message, api_key)[:500]


def _api_error(exc: BaseException, api_key: str) -> str:
    return _redact(f"Anthropic API call failed: {_exc_text(exc)}", api_key)


def _api_exceptions() -> tuple[type[BaseException], ...]:
    exceptions: list[type[BaseException]] = [
        OSError,
        TimeoutError,
        ConnectionError,
    ]
    if anthropic is not None:
        exceptions.append(anthropic.APIError)
    return tuple(exceptions)


class _InvalidOutput(Exception):
    pass

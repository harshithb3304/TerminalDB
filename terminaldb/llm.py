"""LLM abstraction — Ollama and MLX via OpenAI-compatible chat completions."""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any


# ---------------------------------------------------------------------------
# Custom exception — raised only for connectivity/auth failures
# ---------------------------------------------------------------------------

class LLMError(RuntimeError):
    """Raised when the LLM backend is unreachable or returns an auth error."""


# ---------------------------------------------------------------------------
# Backend configuration
# ---------------------------------------------------------------------------

def _backend() -> str:
    val = os.environ.get("TDB_LLM", "ollama").lower()
    if val in ("ollama", "mlx"):
        return val
    print(f"[tdb] Unknown TDB_LLM value '{val}', defaulting to 'ollama'", flush=True)
    return "ollama"


def _base_url() -> str:
    if _backend() == "mlx":
        return os.environ.get("TDB_MLX_HOST", "http://localhost:8080") + "/v1"
    return os.environ.get("TDB_OLLAMA_HOST", "http://localhost:11434") + "/v1"


def _model() -> str:
    if _backend() == "mlx":
        return os.environ.get("TDB_MLX_MODEL", "mlx-community/Llama-3.2-3B-Instruct-4bit")
    return os.environ.get("TDB_OLLAMA_MODEL", "llama3.2")


# ---------------------------------------------------------------------------
# HTTP chat call (OpenAI-compatible)
# ---------------------------------------------------------------------------

def _chat(prompt: str) -> str:
    payload = json.dumps({
        "model": _model(),
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "temperature": 0.2,
    }).encode()

    req = urllib.request.Request(
        f"{_base_url()}/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
            return data["choices"][0]["message"]["content"].strip()
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:300]
        raise LLMError(
            f"{_backend()} returned HTTP {e.code}.\n"
            f"Is the server running? Is the model '{_model()}' pulled?\n{body}"
        )
    except urllib.error.URLError as e:
        backend = _backend()
        host    = _base_url()
        raise LLMError(
            f"Cannot reach {backend} at {host}.\n"
            f"Start it with: {'ollama serve' if backend == 'ollama' else 'mlx_lm.server --model ' + _model()}\n"
            f"Reason: {e.reason}"
        )


# ---------------------------------------------------------------------------
# JSON repair + extraction
# ---------------------------------------------------------------------------

def _repair_json(text: str) -> str:
    # Missing opening quote on string values: "key": value" → "key": "value"
    text = re.sub(r':\s*([A-Za-z][^"\n,\]{}]*)"', r': "\1"', text)
    # Trailing commas before ] or }
    text = re.sub(r',\s*([\]}])', r'\1', text)
    return text


def _extract_json(text: str) -> Any:
    cleaned = re.sub(r"```(?:json)?\s*", "", text).replace("```", "").strip()
    start   = min(
        (cleaned.find(c) for c in ["{", "["] if c in cleaned),
        default=0,
    )
    snippet = cleaned[start:]
    try:
        return json.loads(snippet)
    except json.JSONDecodeError:
        return json.loads(_repair_json(snippet))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def enrich_command(command: str) -> dict:
    """Return {tags: [...], purpose: str} for a terminal command."""
    prompt = f"""You are a terminal command metadata generator.
Given a shell command, return ONLY a JSON object with exactly two fields:
- "tags": array of 2-5 lowercase keywords (primary tool MUST be first, e.g. "kubectl", "docker", "git")
- "purpose": one concise sentence describing what this command does

Return ONLY the JSON object. No explanation. No markdown.

Command: {command}"""

    raw = _chat(prompt)
    print(f"[tdb:llm] enrich raw:\n{raw[:300]}", flush=True)
    try:
        result  = _extract_json(raw)
        tags    = result.get("tags", [])
        purpose = result.get("purpose", "")
        if isinstance(tags, list) and isinstance(purpose, str):
            return {"tags": tags[:5], "purpose": purpose}
    except (json.JSONDecodeError, AttributeError, ValueError) as e:
        print(f"[tdb:llm] enrich parse failed: {e}", flush=True)

    return {"tags": [], "purpose": ""}


def search_with_intent(query: str, records: list[dict]) -> dict:
    """Rank stored records by relevance and suggest new commands."""
    if not records:
        return {"ranked_ids": [], "suggestions": suggest_only(query)}

    index = "\n".join(
        f"ID {r['id']}: {r['command']} | tags: {r['tags']} | {r['purpose']}"
        for r in records
    )

    prompt = f"""You are a terminal command search engine.

User intent: "{query}"

Stored commands:
{index}

Return ONLY a JSON object with:
- "ranked_ids": array of IDs that are DIRECTLY relevant to the intent (empty if none truly match)
- "suggestions": array of 3-5 objects {{command, why}} for NEW commands relevant to the intent

Only include an ID if the command is genuinely useful for the stated intent.
Return ONLY JSON. No markdown. No explanation."""

    raw = _chat(prompt)
    print(f"[tdb:llm] search raw:\n{raw[:500]}", flush=True)
    try:
        result = _extract_json(raw)
        return {
            "ranked_ids":  result.get("ranked_ids", []),
            "suggestions": result.get("suggestions", []),
        }
    except (json.JSONDecodeError, AttributeError, ValueError) as e:
        print(f"[tdb:llm] search parse failed: {e}", flush=True)
        return {"ranked_ids": [], "suggestions": []}


def suggest_only(query: str) -> list:
    """Return AI-suggested commands when the DB has no relevant matches."""
    prompt = f"""Suggest 3-5 useful terminal commands for this intent: "{query}"

Return ONLY a JSON array of objects with fields: "command" and "why" (one sentence).
No markdown. No explanation."""

    raw = _chat(prompt)
    print(f"[tdb:llm] suggest raw:\n{raw[:300]}", flush=True)
    try:
        result = _extract_json(raw)
        if isinstance(result, list):
            return result
        return result.get("suggestions", [])
    except (json.JSONDecodeError, AttributeError, ValueError) as e:
        print(f"[tdb:llm] suggest parse failed: {e}", flush=True)
        return []

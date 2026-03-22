import json
import os
import re
import sys

from google import genai

_client = None
_MODEL  = "gemini-2.0-flash"


def _get_client():
    global _client
    if _client is None:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            print("[error] GEMINI_API_KEY environment variable is not set.")
            sys.exit(1)
        _client = genai.Client(api_key=api_key)
    return _client


def _call(prompt: str) -> str:
    client   = _get_client()
    response = client.models.generate_content(model=_MODEL, contents=prompt)
    return response.text.strip()


def _extract_json(text: str):
    """Extract JSON from a response that may include markdown fences."""
    cleaned = re.sub(r"```(?:json)?\s*", "", text).replace("```", "").strip()
    return json.loads(cleaned)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def enrich_command(command: str) -> dict:
    """
    Ask Gemini to generate tags and a purpose for the given command.
    Returns {"tags": [...], "purpose": "..."}.
    """
    prompt = f"""You are a terminal command analyst.
Given the terminal command below, respond with ONLY a JSON object (no markdown, no explanation).
The JSON must have exactly two keys:
  - "tags": an array of 2–5 lowercase keyword strings (e.g. "docker", "networking", "debugging")
  - "purpose": a single concise sentence explaining what the command does

Command: {command}"""

    raw = _call(prompt)
    try:
        result  = _extract_json(raw)
        tags    = result.get("tags", [])
        purpose = result.get("purpose", "")
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",")]
        return {"tags": tags[:5], "purpose": purpose}
    except (json.JSONDecodeError, AttributeError):
        return {"tags": [], "purpose": raw[:200]}


def search_with_intent(query: str, stored_commands: list[dict]) -> dict:
    """
    Use Gemini to:
    1. Rank stored commands by relevance to the query intent.
    2. Suggest 3–5 new terminal commands for the intent.

    Returns {"ranked_ids": [...], "suggestions": [...]}.
    """
    compact = [
        {
            "id":      r["id"],
            "command": r["command"],
            "tags":    r["tags"],
            "purpose": r["purpose"],
        }
        for r in stored_commands
    ]

    prompt = f"""You are a terminal command search assistant.

User query: "{query}"

Stored commands (JSON array):
{json.dumps(compact, indent=2)}

Tasks:
1. Identify the user's intent from the query.
2. Return the IDs of stored commands that are relevant to that intent, ordered by relevance (most relevant first). Only include IDs that actually exist in the list above.
3. Suggest 3–5 new terminal commands that would help accomplish the intent (these may differ from the stored ones).

Respond with ONLY a JSON object with exactly two keys:
  - "ranked_ids": array of integer IDs from the stored commands, ordered by relevance
  - "suggestions": array of objects, each with "command" (string) and "why" (one sentence)

No markdown, no explanation — raw JSON only."""

    raw = _call(prompt)
    try:
        result = _extract_json(raw)
        return {
            "ranked_ids":  result.get("ranked_ids", []),
            "suggestions": result.get("suggestions", []),
        }
    except (json.JSONDecodeError, AttributeError):
        return {"ranked_ids": [], "suggestions": []}

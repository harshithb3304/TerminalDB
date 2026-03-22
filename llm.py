"""
LLM abstraction — supports Gemini, Ollama, and MLX (Apple Silicon native).

Auto-detection order:
  1. TDB_LLM=gemini  → Gemini API  (needs GEMINI_API_KEY)
  2. TDB_LLM=mlx     → mlx-lm      (needs: pip install mlx-lm && mlx_lm.server ...)
  3. TDB_LLM=ollama  → Ollama      (needs Ollama running)
  4. TDB_LLM not set → Gemini if key present, else MLX server if up, else Ollama

Env vars:
  TDB_LLM            = gemini | mlx | ollama
  GEMINI_API_KEY     = <key>
  TDB_OLLAMA_MODEL   = llama3.2  (default)
  TDB_OLLAMA_HOST    = http://localhost:11434  (default)
  TDB_MLX_MODEL      = mlx-community/Llama-3.2-3B-Instruct-4bit  (default)
  TDB_MLX_HOST       = http://localhost:8080  (default)
"""
import json
import os
import re
import sys
import urllib.error
import urllib.request


# ---------------------------------------------------------------------------
# Backend selection
# ---------------------------------------------------------------------------

def _backend() -> str:
    explicit = os.environ.get("TDB_LLM", "").lower()
    if explicit in ("gemini", "ollama", "mlx"):
        return explicit
    if os.environ.get("GEMINI_API_KEY"):
        return "gemini"
    # Default to mlx on Apple Silicon, ollama otherwise
    import platform
    if platform.system() == "Darwin" and platform.machine() == "arm64":
        return "mlx"
    return "ollama"


def _call(prompt: str) -> str:
    b = _backend()
    if b == "gemini":
        return _gemini_call(prompt)
    if b == "mlx":
        return _mlx_call(prompt)
    return _ollama_call(prompt)


# ---------------------------------------------------------------------------
# Gemini backend
# ---------------------------------------------------------------------------

_gemini_client = None
_GEMINI_MODEL  = "gemini-1.5-flash"


def _gemini_call(prompt: str) -> str:
    global _gemini_client
    if _gemini_client is None:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            _die("GEMINI_API_KEY is not set.")
        try:
            from google import genai
            _gemini_client = genai.Client(api_key=api_key)
        except ImportError:
            _die("google-genai not installed. Run: pip3 install google-genai")

    try:
        response = _gemini_client.models.generate_content(
            model=_GEMINI_MODEL, contents=prompt
        )
        return response.text.strip()
    except Exception as e:
        msg = str(e)
        if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
            _die(
                "Gemini quota exceeded.\n\n"
                "Switch to local MLX (works great on M5):\n"
                "  pip3 install mlx-lm\n"
                "  mlx_lm.server --model mlx-community/Llama-3.2-3B-Instruct-4bit &\n"
                "  export TDB_LLM=mlx"
            )
        raise


# ---------------------------------------------------------------------------
# MLX backend  (Apple Silicon native — recommended for M1/M2/M3/M4/M5)
# ---------------------------------------------------------------------------

def _mlx_host() -> str:
    return os.environ.get("TDB_MLX_HOST", "http://localhost:8080").rstrip("/")

def _mlx_model() -> str:
    return os.environ.get("TDB_MLX_MODEL", "mlx-community/Llama-3.2-3B-Instruct-4bit")


def _mlx_call(prompt: str) -> str:
    host  = _mlx_host()
    model = _mlx_model()
    url   = f"{host}/v1/chat/completions"

    payload = json.dumps({
        "model":    model,
        "messages": [{"role": "user", "content": prompt}],
        "stream":   False,
    }).encode()

    req = urllib.request.Request(
        url,
        data    = payload,
        headers = {"Content-Type": "application/json"},
        method  = "POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
            return data["choices"][0]["message"]["content"].strip()
    except urllib.error.URLError as e:
        if "Connection refused" in str(e) or "refused" in str(e).lower():
            _die(
                f"mlx-lm server is not running at {host}.\n\n"
                "Start it with:\n"
                "  mlx_lm.server --model mlx-community/Llama-3.2-3B-Instruct-4bit\n\n"
                "First time setup:\n"
                "  pip3 install mlx-lm\n"
                "  mlx_lm.server --model mlx-community/Llama-3.2-3B-Instruct-4bit\n"
                "  export TDB_LLM=mlx\n\n"
                "Model downloads automatically on first run (~2 GB)."
            )
        raise
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode())
            msg  = body.get("error", {}).get("message", str(e))
        except Exception:
            msg = str(e)
        _die(f"mlx-lm error {e.code}: {msg}")


# ---------------------------------------------------------------------------
# Ollama backend
# ---------------------------------------------------------------------------

def _ollama_model() -> str:
    return os.environ.get("TDB_OLLAMA_MODEL", "llama3.2")

def _ollama_host() -> str:
    return os.environ.get("TDB_OLLAMA_HOST", "http://localhost:11434").rstrip("/")


def _ollama_call(prompt: str) -> str:
    host  = _ollama_host()
    model = _ollama_model()
    url   = f"{host}/api/generate"

    payload = json.dumps({
        "model":  model,
        "prompt": prompt,
        "stream": False,
    }).encode()

    req = urllib.request.Request(
        url,
        data    = payload,
        headers = {"Content-Type": "application/json"},
        method  = "POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
            return data.get("response", "").strip()
    except urllib.error.HTTPError as e:
        try:
            body      = json.loads(e.read().decode())
            ollama_msg = body.get("error", str(e))
        except Exception:
            ollama_msg = str(e)
        if e.code == 404 or "not found" in ollama_msg.lower():
            _die(f"Ollama model '{model}' not found. Run: ollama pull {model}")
        _die(f"Ollama error {e.code}: {ollama_msg}")
    except urllib.error.URLError as e:
        if "Connection refused" in str(e) or "refused" in str(e).lower():
            _die(f"Ollama not running at {host}. Run: ollama serve")
        raise


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _repair_json(text: str) -> str:
    """Fix common JSON issues produced by small local models."""
    # Missing opening quote on string values:  "key": some text"  →  "key": "some text"
    text = re.sub(r':\s*([A-Za-z][^"\n,\]{}]*)"', r': "\1"', text)
    # Trailing commas before ] or }
    text = re.sub(r',\s*([\]}])', r'\1', text)
    return text


def _extract_json(text: str):
    """Strip markdown fences, attempt repair, and parse JSON."""
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


class LLMError(RuntimeError):
    """Raised when the LLM backend is unavailable or misconfigured."""
    pass


def _die(msg: str):
    """In CLI context raises + exits. In web context just raises LLMError."""
    raise LLMError(msg)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def suggest_only(query: str) -> list[dict]:
    """Ask AI for suggestions when there are no stored commands to rank."""
    prompt = f"""You are a terminal command expert.

The user is looking for terminal commands to: "{query}"

Suggest 5 practical, commonly-used terminal commands that DIRECTLY accomplish this goal.
Only suggest commands that are genuinely relevant to the exact tools and intent described.
Do NOT suggest tangentially related commands from different tools.

Respond with ONLY a JSON array of objects, each with:
  - "command": the exact terminal command string (with realistic example arguments where helpful)
  - "why": one sentence explaining precisely what it does

Raw JSON only. No markdown. No explanation outside the JSON."""

    raw = _call(prompt)
    print(f"[tdb:llm] suggest_only raw:\n{raw[:500]}", flush=True)
    try:
        result = _extract_json(raw)
        if isinstance(result, list):
            return result
        return result.get("suggestions", [])
    except (json.JSONDecodeError, AttributeError, ValueError) as e:
        print(f"[tdb:llm] suggest_only parse failed: {e}", flush=True)
        return []  # Don't surface parse errors to the user


def enrich_command(command: str) -> dict:
    prompt = f"""You are a terminal command analyst.
Given the terminal command below, respond with ONLY a JSON object (no markdown, no explanation).
The JSON must have exactly two keys:
  - "tags": an array of 2-4 lowercase keyword strings following these strict rules:
      * First tag MUST be the primary CLI tool name (e.g. "docker", "kubectl", "git", "npm")
      * Remaining tags describe the action/domain (e.g. "exec", "containers", "logs", "networking")
      * Tags must be single words, no phrases
      * Do NOT add generic tags like "terminal", "cli", "command", "linux"
  - "purpose": a single concise sentence (max 15 words) explaining exactly what the command does

Command: {command}"""

    raw = _call(prompt)
    try:
        result  = _extract_json(raw)
        tags    = result.get("tags", [])
        purpose = result.get("purpose", "")
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",")]
        return {"tags": tags[:5], "purpose": purpose}
    except (json.JSONDecodeError, AttributeError, ValueError):
        return {"tags": [], "purpose": raw[:200]}


def search_with_intent(query: str, stored_commands: list[dict]) -> dict:
    compact = [
        {"id": r["id"], "command": r["command"], "tags": r["tags"], "purpose": r["purpose"]}
        for r in stored_commands
    ]

    prompt = f"""You are a terminal command search assistant with strict relevance standards.

User query: "{query}"

Stored commands:
{json.dumps(compact, indent=2)}

Rules:
1. Extract the EXACT tool and action the user is asking about (e.g. "docker" + "exec into container").
2. From the stored commands, return ONLY the IDs of commands that match BOTH the tool AND the intent.
   - If the query is about "docker", do NOT return kubectl or git commands.
   - If the query is about "exec into container", do NOT return commands that just list containers.
   - If no stored command is a good match, return an empty ranked_ids array — do not force matches.
3. Suggest 3-5 new commands that DIRECTLY accomplish the user's exact intent using the correct tool.
   Suggestions must use realistic arguments, not just --help flags.

Respond with ONLY a JSON object (raw JSON, no markdown):
  - "ranked_ids": array of integer IDs of genuinely matching stored commands, best match first
  - "suggestions": array of objects with "command" (string) and "why" (one sentence)"""

    raw = _call(prompt)
    print(f"[tdb:llm] search_with_intent raw:\n{raw[:500]}", flush=True)
    try:
        result = _extract_json(raw)
        return {
            "ranked_ids":  result.get("ranked_ids", []),
            "suggestions": result.get("suggestions", []),
        }
    except (json.JSONDecodeError, AttributeError, ValueError) as e:
        print(f"[tdb:llm] search_with_intent parse failed: {e}", flush=True)
        return {"ranked_ids": [], "suggestions": []}  # Don't surface parse errors

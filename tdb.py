#!/usr/bin/env python3
"""
terminalDB (tdb) — capture, enrich, and semantically search terminal commands.

Commands:
    tdb capture "<command>"   # called automatically by the shell hook
    tdb setup                 # install shell hook into your rc file
    tdb web [--port 7777]     # open the web dashboard
    tdb search "<query>"      # AI-powered search + suggestions
    tdb list                  # list all stored commands
    tdb delete <id>           # delete by id
    tdb add "<command>"       # manually add (bypasses shell hook)
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import typer

import db
import display
import llm
from llm import LLMError

app = typer.Typer(
    name="tdb",
    help="terminalDB — AI-powered terminal command manager",
    add_completion=False,
)

db.init_db()

# Commands that are too trivial to prompt about
_SKIP = {
    "ls", "ll", "la", "l", "cd", "pwd", "clear", "cls", "exit", "logout",
    "history", "man", "echo", "cat", "less", "more", "head", "tail",
    "mkdir", "rmdir", "touch", "cp", "mv", "rm", "ln",
    "which", "where", "type", "alias", "unalias", "export", "env", "printenv",
    "ps", "top", "htop", "kill", "killall",
    "date", "time", "uptime", "whoami", "id", "hostname",
    "true", "false", ":", "source", ".", "exec",
}

TDB_DIR = Path(__file__).parent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _confirm(prompt: str) -> bool:
    try:
        answer = input(prompt).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    return answer in {"y", "yes"}


def _is_trivial(command: str) -> bool:
    """Return True for commands not worth saving."""
    command = command.strip()
    if not command or command.startswith(" "):
        return True
    base = command.split()[0].lstrip("\\")
    # Skip tdb itself
    if base in ("tdb", "python3", "python") and "tdb" in command:
        return True
    return base in _SKIP


def _enrich_and_store(command: str):
    """Enrich via Gemini then save. Called after user confirms."""
    existing = db.find_duplicate(command)
    if existing:
        display.warn(f"Already saved as id={existing['id']} — skipping duplicate.")
        return

    display.info("  Enriching with AI…")
    try:
        enrichment = llm.enrich_command(command)
    except LLMError as e:
        display.error(str(e))
        sys.exit(1)
    tags    = enrichment["tags"]
    purpose = enrichment["purpose"]

    record_id = db.insert_command(command, tags, purpose)

    print(f"  \033[2mpurpose:\033[0m {purpose}")
    print(f"  \033[2mtags:\033[0m    {', '.join(tags)}")
    display.success(f"  Saved as id={record_id}. ✓")


# ---------------------------------------------------------------------------
# Shell hook commands
# ---------------------------------------------------------------------------

@app.command()
def capture(
    command: str = typer.Argument(..., help="The command that just ran (passed by shell hook)")
):
    """
    Called automatically by the shell hook after every command.
    Prompts the user interactively to save it.
    """
    command = command.strip()
    if _is_trivial(command):
        return  # silent — don't interrupt trivial commands

    # Compact inline prompt — keeps it unobtrusive
    print(f"\n\033[2m[tdb]\033[0m \033[1m{command}\033[0m")
    try:
        answer = input("      Save this command? [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return

    if answer in {"y", "yes"}:
        _enrich_and_store(command)
    print()  # breathing room before next prompt


@app.command()
def setup(
    shell: str = typer.Option("auto", help="Shell to configure: zsh, bash, or auto"),
    rc_file: str = typer.Option("", help="Path to rc file (auto-detected if omitted)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print hook code without installing"),
):
    """Install the shell hook so tdb is prompted after every command."""
    tdb_path  = (TDB_DIR / "tdb.py").resolve()
    hook_code = _generate_hook(str(tdb_path), shell, rc_file)

    if dry_run:
        print(hook_code)
        return

    detected_rc = _detect_rc(shell, rc_file)
    if not detected_rc:
        display.error("Could not detect shell rc file. Use --rc-file to specify.")
        raise typer.Exit(1)

    rc = Path(detected_rc).expanduser()
    marker = "# >>> terminalDB hook <<<"

    if rc.exists() and marker in rc.read_text():
        display.warn(f"Hook already installed in {rc}. Nothing to do.")
        return

    block = f"\n{marker}\n{hook_code}\n# <<< terminalDB hook >>>\n"
    with open(rc, "a") as f:
        f.write(block)

    display.success(f"Hook installed in {rc}")
    display.info(f"Run:  source {rc}   (or open a new terminal)")


def _detect_rc(shell: str, override: str) -> str:
    if override:
        return override
    if shell == "auto":
        shell = Path(os.environ.get("SHELL", "/bin/zsh")).name
    if shell == "zsh":
        return "~/.zshrc"
    if shell == "bash":
        rc = "~/.bash_profile" if sys.platform == "darwin" else "~/.bashrc"
        return rc
    return ""


def _generate_hook(tdb_path: str, shell: str, rc_file: str) -> str:
    if shell == "auto":
        shell = Path(os.environ.get("SHELL", "/bin/zsh")).name

    if shell == "zsh":
        return f"""\
# terminalDB — auto-capture shell commands
_tdb_preexec() {{ _TDB_LAST_CMD="$1"; }}
_tdb_precmd() {{
  if [[ -n "$_TDB_LAST_CMD" ]]; then
    local _cmd="$_TDB_LAST_CMD"
    _TDB_LAST_CMD=""
    python3 {tdb_path} capture "$_cmd" </dev/tty >/dev/tty 2>/dev/tty
  fi
}}
autoload -Uz add-zsh-hook
add-zsh-hook preexec _tdb_preexec
add-zsh-hook precmd  _tdb_precmd"""
    else:  # bash
        return f"""\
# terminalDB — auto-capture shell commands
_TDB_LAST_CMD=""
_tdb_debug() {{
  if [[ "$BASH_COMMAND" != _tdb_* && "$BASH_COMMAND" != "python3 {tdb_path}"* ]]; then
    _TDB_LAST_CMD="$BASH_COMMAND"
  fi
}}
_tdb_precmd() {{
  if [[ -n "$_TDB_LAST_CMD" ]]; then
    local _cmd="$_TDB_LAST_CMD"
    _TDB_LAST_CMD=""
    python3 {tdb_path} capture "$_cmd" </dev/tty >/dev/tty 2>/dev/tty
  fi
}}
trap '_tdb_debug' DEBUG
PROMPT_COMMAND="_tdb_precmd${{PROMPT_COMMAND:+;$PROMPT_COMMAND}}\""""


# ---------------------------------------------------------------------------
# Web dashboard
# ---------------------------------------------------------------------------

@app.command()
def web(
    port: int = typer.Option(7777, "--port", "-p", help="Port to listen on"),
    no_browser: bool = typer.Option(False, "--no-browser", help="Don't auto-open browser"),
):
    """Launch the web dashboard."""
    try:
        import web_server  # noqa: F401 — just check it's importable
    except ImportError as e:
        display.error(f"Missing dependency: {e}. Run: pip3 install flask")
        raise typer.Exit(1)

    display.success(f"Starting terminalDB web dashboard on http://localhost:{port}")
    if not no_browser:
        import threading, webbrowser
        threading.Timer(1.0, lambda: webbrowser.open(f"http://localhost:{port}")).start()

    # Import after dep check
    from web_server import create_app
    flask_app = create_app()
    flask_app.run(host="127.0.0.1", port=port, debug=False)


# ---------------------------------------------------------------------------
# Core CLI commands (manual)
# ---------------------------------------------------------------------------

@app.command()
def add(command: str = typer.Argument(..., help="Command to save")):
    """Manually add and enrich a terminal command."""
    command = command.strip()
    if not command:
        display.error("Command cannot be empty.")
        raise typer.Exit(1)

    existing = db.find_duplicate(command)
    if existing:
        display.warn(f"Already saved as id={existing['id']}.")
        if not _confirm("Save again anyway? (y/n): "):
            return

    display.info("Enriching with AI…")
    enrichment = llm.enrich_command(command)
    tags    = enrichment["tags"]
    purpose = enrichment["purpose"]

    preview = {"id": "?", "command": command, "tags": json.dumps(tags), "purpose": purpose, "timestamp": "now"}
    display.section_header("Preview")
    display.print_record(preview)

    if not _confirm("Save? (y/n): "):
        display.info("Discarded.")
        return

    record_id = db.insert_command(command, tags, purpose)
    display.success(f"Saved as id={record_id}.")


@app.command()
def search(query: str = typer.Argument(..., help="Natural language search query")):
    """Semantically search stored commands and get AI suggestions."""
    query = query.strip()
    if not query:
        display.error("Query cannot be empty.")
        raise typer.Exit(1)

    all_records = db.fetch_all_for_search()
    if not all_records:
        display.warn("No commands stored yet. Run some commands in your terminal!")
        return

    display.info(f'Searching: "{query}"  (asking AI…)')
    result      = llm.search_with_intent(query, all_records)
    ranked_ids  = result.get("ranked_ids", [])
    suggestions = result.get("suggestions", [])

    record_map = {r["id"]: r for r in all_records}

    display.section_header("Matched Commands")
    matched = [record_map[rid] for rid in ranked_ids if rid in record_map]
    if not matched:
        matched = db.search_local(query)
    if matched:
        for rec in matched:
            display.print_record(rec)
    else:
        display.warn("No matching commands found.")

    display.section_header("AI-Suggested Commands")
    if suggestions:
        for i, sug in enumerate(suggestions, 1):
            display.print_suggestion(i, sug)
    else:
        display.warn("No suggestions returned.")


@app.command(name="list")
def list_commands():
    """List all stored commands."""
    records = db.fetch_all()
    if not records:
        display.warn("No commands stored yet.")
        return
    display.section_header(f"All Commands ({len(records)})")
    for rec in records:
        display.print_record(rec)


@app.command()
def delete(record_id: int = typer.Argument(..., help="ID of the command to delete")):
    """Delete a stored command by ID."""
    record = db.fetch_by_id(record_id)
    if not record:
        display.error(f"No command with id={record_id}.")
        raise typer.Exit(1)

    display.print_record(record)
    if not _confirm("Delete this? (y/n): "):
        display.info("Cancelled.")
        return

    db.delete_by_id(record_id)
    display.success(f"Deleted id={record_id}.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app()

"""terminalDB CLI — all commands."""
from __future__ import annotations

import re
import sys
from pathlib import Path

import typer
from rich.console import Console

from . import db, display
from . import llm as _llm
from .llm import LLMError

app     = Console(stderr=True)
cli     = typer.Typer(name="tdb", help="AI-powered terminal command history.", add_completion=False)
_SKIP   = frozenset({
    "ls", "ll", "la", "l", "cd", "pwd", "clear", "cls", "exit", "logout",
    "history", "man", "help", "echo", "cat", "less", "more", "head", "tail",
    "which", "whereis", "type", "alias", "unalias", "env", "printenv",
})
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[mGKHF]")


def _sanitize(cmd: str) -> str:
    cmd = _ANSI_RE.sub("", cmd).strip()
    return cmd[:500]  # Hard cap on length


def _is_trivial(cmd: str) -> bool:
    base = cmd.split()[0] if cmd.split() else ""
    return (
        not cmd
        or base in _SKIP
        or cmd.startswith("tdb ")
        or cmd.startswith("python3 tdb")
        or len(cmd) < 4
    )


def _enrich_and_store(command: str) -> None:
    display.info("  Enriching with AI…")
    try:
        meta    = _llm.enrich_command(command)
        tags    = meta.get("tags", [])
        purpose = meta.get("purpose", "")
    except LLMError as e:
        display.warn(f"  AI unavailable ({e}); saving without tags.")
        tags, purpose = [], ""

    record_id = db.insert_command(command, tags, purpose)
    display.success(f"  Saved #{record_id}")
    if purpose:
        display.info(f"  {purpose}")
    if tags:
        display.info("  " + "  ".join(f"#{t}" for t in tags))


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

@cli.command()
def add(command: str = typer.Argument(..., help="Command to store.")):
    """Manually add a command to the database."""
    db.init_db()
    command = _sanitize(command)
    if not command:
        display.error("Empty command.")
        raise typer.Exit(1)

    dup = db.find_duplicate(command)
    if dup:
        display.warn(f"  Already stored as #{dup['id']}.")
        raise typer.Exit(0)

    _enrich_and_store(command)


@cli.command()
def capture(command: str = typer.Argument(..., help="Command to maybe save (called by shell hook).")):
    """Prompt the user to save a command — called automatically by the shell hook."""
    db.init_db()
    command = _sanitize(command)
    if _is_trivial(command):
        return

    dup = db.find_duplicate(command)
    if dup:
        return  # Silently skip duplicates in hook mode

    print(f"\n\033[2m[tdb]\033[0m \033[38;5;83m{command}\033[0m")
    try:
        answer = input("      Save this command? [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return

    if answer in {"y", "yes"}:
        _enrich_and_store(command)
    print()


@cli.command("list")
def list_cmds(limit: int = typer.Option(50, "--limit", "-n", help="Max records to show.")):
    """List stored commands."""
    db.init_db()
    records = db.fetch_all()[:limit]
    if not records:
        display.warn("No commands stored yet. Run any command and say 'y' to save it.")
        return
    display.section_header(f"{len(records)} commands")
    for r in records:
        display.print_record(r)


@cli.command()
def search(query: str = typer.Argument(..., help="Natural language search query.")):
    """Semantic search over stored commands."""
    db.init_db()
    all_records = db.fetch_all()

    display.section_header("Searching…")
    try:
        result      = _llm.search_with_intent(query, all_records)
        ranked_ids  = result.get("ranked_ids", [])
        suggestions = result.get("suggestions", [])
    except LLMError as e:
        display.error(f"LLM error: {e}")
        # Fall back to local search
        matched = db.search_local(query)
        display.section_header("Local matches (AI unavailable)")
        for r in matched:
            display.print_record(r)
        return

    id_map  = {r["id"]: r for r in all_records}
    matched = [id_map[i] for i in ranked_ids if i in id_map]

    if matched:
        display.section_header("Matched commands")
        for r in matched:
            display.print_record(r)
    else:
        display.warn("No matches in your history.")

    if suggestions:
        display.section_header("AI suggestions")
        for i, s in enumerate(suggestions, 1):
            display.print_suggestion(s, i)


@cli.command()
def delete(record_id: int = typer.Argument(..., help="ID of command to delete.")):
    """Delete a stored command by ID."""
    db.init_db()
    ok = db.delete_by_id(record_id)
    if ok:
        display.success(f"Deleted #{record_id}.")
    else:
        display.error(f"No command with ID {record_id}.")
        raise typer.Exit(1)


@cli.command()
def web(port: int = typer.Option(7777, "--port", "-p", help="Port to listen on.")):
    """Launch the web dashboard."""
    db.init_db()
    from .web.server import create_app
    flask_app = create_app()
    print(f"\033[38;5;83mStarting terminalDB dashboard → http://localhost:{port}\033[0m")
    print("Press Ctrl+C to stop.\n")
    try:
        flask_app.run(host="127.0.0.1", port=port, debug=False)
    except KeyboardInterrupt:
        print("\nStopped.")


@cli.command()
def setup(
    shell:   str  = typer.Option("zsh", "--shell", "-s", help="Shell: zsh or bash"),
    session: bool = typer.Option(False, "--session", help="Print hook for eval (current session only)"),
):
    """Install the shell hook so tdb prompts after every command."""
    hook_src = _load_hook_template(shell)
    if hook_src is None:
        display.error(f"Unsupported shell: {shell}. Choose 'zsh' or 'bash'.")
        raise typer.Exit(1)

    if session:
        # Just print the hook — user runs: eval "$(tdb setup --session)"
        print(hook_src)
        return

    _install_hook(shell, hook_src)


@cli.command()
def unsetup(shell: str = typer.Option("zsh", "--shell", "-s", help="Shell: zsh or bash")):
    """Remove the shell hook."""
    rc = Path.home() / (".zshrc" if shell == "zsh" else ".bashrc")
    if not rc.exists():
        display.warn(f"{rc} not found.")
        return

    text  = rc.read_text()
    start = "# >>> terminalDB hook >>>"
    end   = "# <<< terminalDB hook <<<"

    if start not in text:
        display.warn("terminalDB hook not found in shell config.")
        return

    cleaned = re.sub(
        re.escape(start) + r".*?" + re.escape(end),
        "",
        text,
        flags=re.DOTALL,
    ).strip() + "\n"

    rc.write_text(cleaned)
    display.success(f"Hook removed from {rc}. Run: source {rc}")


@cli.command()
def status():
    """Show current configuration."""
    import os

    db.init_db()
    records = db.fetch_all()

    backend = os.environ.get("TDB_LLM", "ollama")
    print(f"\n  DB path   : {db.DB_PATH}")
    print(f"  Commands  : {len(records)}")
    print(f"  LLM       : {backend}")
    if backend == "mlx":
        print(f"  MLX host  : {os.environ.get('TDB_MLX_HOST', 'http://localhost:8080')}")
        print(f"  MLX model : {os.environ.get('TDB_MLX_MODEL', 'mlx-community/Llama-3.2-3B-Instruct-4bit')}")
    else:
        print(f"  Ollama    : {os.environ.get('TDB_OLLAMA_HOST', 'http://localhost:11434')}")
        print(f"  Model     : {os.environ.get('TDB_OLLAMA_MODEL', 'llama3.2')}")
    print()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_hook_template(shell: str) -> str | None:
    import importlib.resources as pkg
    try:
        fname = f"tdb.{shell}"
        ref   = pkg.files("terminaldb") / "shell" / fname
        return ref.read_text()
    except (FileNotFoundError, TypeError):
        return None


def _install_hook(shell: str, hook_src: str) -> None:
    hook_dir  = Path.home() / ".terminaldb" / "shell"
    hook_dir.mkdir(parents=True, exist_ok=True)
    hook_file = hook_dir / f"tdb.{shell}"
    hook_file.write_text(hook_src)

    rc        = Path.home() / (".zshrc" if shell == "zsh" else ".bashrc")
    start     = "# >>> terminalDB hook >>>"
    end       = "# <<< terminalDB hook <<<"
    source_ln = f"source {hook_file}"
    block     = f"\n{start}\n{source_ln}\n{end}\n"

    existing  = rc.read_text() if rc.exists() else ""
    if start in existing:
        display.warn("Hook already installed. Run 'tdb unsetup' first to reinstall.")
        return

    with rc.open("a") as f:
        f.write(block)

    display.success(f"Hook installed → {rc}")
    display.info(f"Run:  source {rc}")


def main() -> None:
    db.init_db()
    cli()

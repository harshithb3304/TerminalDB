"""Terminal display helpers using ANSI escape codes."""
from __future__ import annotations
import json

_RESET  = "\033[0m"
_BOLD   = "\033[1m"
_GREEN  = "\033[38;5;83m"
_CYAN   = "\033[38;5;81m"
_YELLOW = "\033[38;5;220m"
_RED    = "\033[38;5;203m"
_DIM    = "\033[2m"


def info(msg: str)    -> None: print(f"{_CYAN}{msg}{_RESET}")
def success(msg: str) -> None: print(f"{_GREEN}{msg}{_RESET}")
def warn(msg: str)    -> None: print(f"{_YELLOW}{msg}{_RESET}")
def error(msg: str)   -> None: print(f"{_RED}{msg}{_RESET}")


def print_record(record: dict, index: int | None = None) -> None:
    tags = record.get("tags", [])
    if isinstance(tags, str):
        try:
            tags = json.loads(tags)
        except json.JSONDecodeError:
            tags = []
    tag_str = "  ".join(f"{_CYAN}#{t}{_RESET}" for t in tags)
    prefix  = f"{_DIM}#{record['id']}{_RESET}  " if index is None else f"{_DIM}{index}.{_RESET}  "
    print(f"\n{prefix}{_GREEN}{_BOLD}$ {record['command']}{_RESET}")
    if record.get("purpose"):
        print(f"   {_YELLOW}{record['purpose']}{_RESET}")
    if tag_str:
        print(f"   {tag_str}")
    if record.get("timestamp"):
        print(f"   {_DIM}{record['timestamp']}{_RESET}")


def print_suggestion(suggestion: dict, index: int) -> None:
    print(f"\n  {_DIM}{index}.{_RESET}  {_GREEN}$ {suggestion.get('command', '')}{_RESET}")
    why = suggestion.get("why") or suggestion.get("purpose", "")
    if why:
        print(f"     {_YELLOW}{why}{_RESET}")


def section_header(title: str) -> None:
    print(f"\n{_CYAN}{_BOLD}{'─' * 4} {title} {'─' * 4}{_RESET}")

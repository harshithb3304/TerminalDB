"""
Shared display helpers — keeps tdb.py clean.
All output goes through these so styling is consistent.
"""
import json


_RESET  = "\033[0m"
_BOLD   = "\033[1m"
_DIM    = "\033[2m"
_CYAN   = "\033[36m"
_GREEN  = "\033[32m"
_YELLOW = "\033[33m"
_BLUE   = "\033[34m"
_RED    = "\033[31m"
_MAGENTA = "\033[35m"


def _tags_str(tags_raw) -> str:
    if isinstance(tags_raw, str):
        try:
            tags = json.loads(tags_raw)
        except json.JSONDecodeError:
            tags = [tags_raw]
    else:
        tags = tags_raw
    return "  ".join(f"{_CYAN}#{t}{_RESET}" for t in tags) if tags else f"{_DIM}(none){_RESET}"


def print_record(record: dict, prefix: str = ""):
    id_str      = f"{_DIM}[{record['id']}]{_RESET}"
    ts_str      = f"{_DIM}{record.get('timestamp', '')}{_RESET}"
    cmd_str     = f"{_BOLD}{_GREEN}{record['command']}{_RESET}"
    purpose_str = f"{_YELLOW}{record.get('purpose', '')}{_RESET}"
    tags_str    = _tags_str(record.get("tags", "[]"))

    print(f"{prefix}{id_str} {ts_str}")
    print(f"{prefix}  {cmd_str}")
    print(f"{prefix}  {purpose_str}")
    print(f"{prefix}  {tags_str}")
    print()


def print_suggestion(index: int, suggestion: dict):
    cmd  = suggestion.get("command", "")
    why  = suggestion.get("why", "")
    print(f"  {_BOLD}{_MAGENTA}{index}. {cmd}{_RESET}")
    print(f"     {_DIM}{why}{_RESET}")
    print()


def section_header(title: str):
    bar = "─" * (len(title) + 4)
    print(f"\n{_BOLD}{_BLUE}┌{bar}┐{_RESET}")
    print(f"{_BOLD}{_BLUE}│  {title}  │{_RESET}")
    print(f"{_BOLD}{_BLUE}└{bar}┘{_RESET}\n")


def info(msg: str):
    print(f"{_CYAN}{msg}{_RESET}")


def success(msg: str):
    print(f"{_GREEN}{msg}{_RESET}")


def warn(msg: str):
    print(f"{_YELLOW}{msg}{_RESET}")


def error(msg: str):
    print(f"{_RED}{msg}{_RESET}")

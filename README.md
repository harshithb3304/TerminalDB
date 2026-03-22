# terminalDB (tdb)

AI-powered terminal command manager. Runs a shell hook that prompts you to save commands as you use them, enriches them with AI-generated tags and purpose, and lets you search them semantically.

---

## Quick reference

```
tdb setup                   install shell hook into ~/.zshrc or ~/.bashrc
tdb web                     open web dashboard at http://localhost:7777
tdb web --port 9000         web dashboard on a custom port
tdb search "query"          AI-powered search + suggestions in terminal
tdb list                    list all saved commands
tdb add "command"           manually save a command
tdb delete <id>             delete a saved command by id
tdb setup --dry-run         print hook code without installing
tdb setup --shell bash      install for bash instead of zsh
```

---

## Start / Stop

### Shell hook (auto-capture)

```bash
# Install once
python3 tdb.py setup
source ~/.zshrc

# Disable for current session only
add-zsh-hook -d preexec _tdb_preexec
add-zsh-hook -d precmd  _tdb_precmd

# Re-enable
source ~/.zshrc

# Uninstall permanently — remove these lines from ~/.zshrc:
# >>> terminalDB hook <<<
# ... (the hook block)
# <<< terminalDB hook >>>
```

### Web dashboard

```bash
# Start
python3 tdb.py web

# Stop
Ctrl+C
```

### MLX server (local AI — Apple Silicon)

```bash
# Start (leave running in a terminal tab)
mlx_lm.server --model mlx-community/Llama-3.2-3B-Instruct-4bit

# Stop
Ctrl+C
```

---

## Setup

### 1. Install dependencies

```bash
cd terminalDB
pip3 install -r requirements.txt
```

### 2. Choose an AI backend

**Option A — MLX (recommended on Apple Silicon, no quota, free)**
```bash
pip3 install mlx-lm
mlx_lm.server --model mlx-community/Llama-3.2-3B-Instruct-4bit &
export TDB_LLM=mlx
```

**Option B — Gemini API**
```bash
export GEMINI_API_KEY="your-key-here"
# key at https://aistudio.google.com/app/apikey
```

### 3. Install the shell hook

```bash
python3 tdb.py setup
source ~/.zshrc
```

After this, every non-trivial command you run will show:
```
[tdb] kubectl get pods
      Save this command? [y/N]
```

### 4. (Optional) alias tdb globally

```bash
echo 'alias tdb="python3 /Users/harshithb/akto/terminalDB/tdb.py"' >> ~/.zshrc
source ~/.zshrc
# then use: tdb web, tdb list, tdb search "query" etc.
```

---

## Web UI

```bash
python3 tdb.py web
# opens http://localhost:7777
```

| Action | How |
|---|---|
| AI search | Type query → press **Enter** |
| Filter by tag | Type `#docker` → results filter live |
| Click a tag | Instantly filters by that tag |
| Clear search | Press **Esc** |
| Copy command | Click **Copy** on any card |
| Delete command | Click **Delete** → confirm |

---

## Storage

SQLite file at `terminalDB/tdb.sqlite` — no server, no process. Python reads/writes directly.

```bash
# inspect raw data
sqlite3 ~/akto/terminalDB/tdb.sqlite "SELECT id, command, tags FROM commands;"
```

Schema:
```sql
CREATE TABLE commands (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    command   TEXT NOT NULL,
    tags      TEXT NOT NULL DEFAULT '[]',  -- JSON array, first tag = tool name
    purpose   TEXT NOT NULL DEFAULT '',
    timestamp TEXT NOT NULL               -- ISO-8601 UTC
);
```

---

## Environment variables

| Variable           | Default                | Description                          |
|--------------------|------------------------|--------------------------------------|
| `TDB_LLM`          | auto-detect            | `gemini` / `mlx` / `ollama`          |
| `GEMINI_API_KEY`   | —                      | Required for Gemini backend          |
| `TDB_MLX_HOST`     | `http://localhost:8080`| mlx-lm server URL                   |
| `TDB_MLX_MODEL`    | `mlx-community/Llama-3.2-3B-Instruct-4bit` | MLX model name  |
| `TDB_OLLAMA_HOST`  | `http://localhost:11434` | Ollama server URL                  |
| `TDB_OLLAMA_MODEL` | `llama3.2`             | Ollama model name                    |

---

## Project layout

```
terminalDB/
├── tdb.py           # CLI entry point (Typer) — all commands
├── db.py            # SQLite operations
├── llm.py           # LLM abstraction (Gemini / MLX / Ollama)
├── web_server.py    # Flask server + embedded HTML/CSS/JS dashboard
├── display.py       # Coloured terminal output helpers
├── requirements.txt
├── tdb.sqlite       # Created automatically on first run
└── README.md
```

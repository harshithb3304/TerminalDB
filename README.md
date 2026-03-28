# terminalDB

AI-powered terminal command history with semantic search. A shell hook captures commands as you run them, a local LLM enriches each one with tags and a purpose description, and a CLI + web dashboard let you find any command later using natural language.

**100% local. No cloud. No API keys.**

---

## Install

### Option A — from GitHub (recommended)

```bash
pip install git+https://github.com/YOUR_USERNAME/terminalDB.git
```

> Replace `YOUR_USERNAME` with your GitHub username after pushing the repo.

### Option B — local development clone

```bash
git clone https://github.com/YOUR_USERNAME/terminalDB.git
cd terminalDB
pip install -e .
```

---

## Quick start

### 1. Choose an AI backend

**MLX — recommended on Apple Silicon (M1/M2/M3/M4, fast, free)**

```bash
# Install mlx-lm if you haven't
pip install mlx-lm

# Launch the included script (model already cached after first run)
./start-mlx.sh

# In a new terminal, tell tdb to use MLX
export TDB_LLM=mlx
```

Add to `~/.zshrc` to persist:
```bash
export TDB_LLM=mlx
export TDB_MLX_HOST=http://127.0.0.1:8080
```

**Ollama — works on any machine**

```bash
# Install from https://ollama.com, then:
ollama pull llama3.2
ollama serve
# TDB_LLM defaults to ollama, no export needed
```

### 2. Install the shell hook

```bash
# zsh (default)
tdb setup
source ~/.zshrc

# bash
tdb setup --shell bash
source ~/.bashrc
```

After this, every non-trivial command you run prompts:

```
[tdb] kubectl get pods -n production
      Save this command? [y/N]
```

Press `y` to save. The LLM adds tags and a purpose description automatically.

### 4. Search

```bash
# AI-powered semantic search
tdb search "list kubernetes pods"

# Web dashboard
tdb web
# opens http://localhost:7777
```

---

## CLI commands

| Command | Description |
|---|---|
| `tdb add "command"` | Manually save a command |
| `tdb capture "command"` | Prompt to save (called by shell hook) |
| `tdb list` | List all stored commands |
| `tdb list -n 20` | List the 20 most recent commands |
| `tdb search "query"` | AI semantic search + suggestions |
| `tdb delete <id>` | Delete a command by ID |
| `tdb web` | Launch web dashboard on port 7777 |
| `tdb web --port 9000` | Launch web dashboard on a custom port |
| `tdb setup` | Install zsh shell hook |
| `tdb setup --shell bash` | Install bash shell hook |
| `tdb setup --session` | Print hook for `eval` (current session only) |
| `tdb unsetup` | Remove zsh shell hook |
| `tdb unsetup --shell bash` | Remove bash shell hook |
| `tdb status` | Show configuration and DB stats |

---

## Web UI

```bash
tdb web
# Dashboard at http://localhost:7777
```

| Action | How |
|---|---|
| AI search | Type a query and press **Enter** |
| Live filter | Type any text — cards filter instantly |
| Filter by tag | Type `#docker` or click any tag pill |
| Copy a command | Click the **Copy** button on any card |
| Delete a command | Click **Delete** and confirm |
| Refresh | Click the **Refresh** button in the header |

---

## LLM configuration

### Ollama

```bash
export TDB_LLM=ollama                            # default
export TDB_OLLAMA_HOST=http://localhost:11434    # default
export TDB_OLLAMA_MODEL=llama3.2                 # default
```

Pull a different model:

```bash
ollama pull mistral
export TDB_OLLAMA_MODEL=mistral
```

### MLX (Apple Silicon)

```bash
export TDB_LLM=mlx
export TDB_MLX_HOST=http://localhost:8080        # default
export TDB_MLX_MODEL=mlx-community/Llama-3.2-3B-Instruct-4bit  # default
```

Start the server:

```bash
mlx_lm.server --model mlx-community/Llama-3.2-3B-Instruct-4bit
```

### All environment variables

| Variable | Default | Description |
|---|---|---|
| `TDB_LLM` | `ollama` | Backend: `ollama` or `mlx` |
| `TDB_OLLAMA_HOST` | `http://localhost:11434` | Ollama server URL |
| `TDB_OLLAMA_MODEL` | `llama3.2` | Ollama model name |
| `TDB_MLX_HOST` | `http://localhost:8080` | MLX server URL |
| `TDB_MLX_MODEL` | `mlx-community/Llama-3.2-3B-Instruct-4bit` | MLX model name |

---

## Storage

Commands are stored in `~/.terminaldb/tdb.sqlite`. No server process is required — Python reads and writes the file directly.

```bash
# Inspect raw data
sqlite3 ~/.terminaldb/tdb.sqlite "SELECT id, command, tags, purpose FROM commands;"
```

Schema:

```sql
CREATE TABLE commands (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    command   TEXT    NOT NULL,
    tags      TEXT    NOT NULL DEFAULT '[]',   -- JSON array, first tag = primary tool
    purpose   TEXT    NOT NULL DEFAULT '',
    timestamp TEXT    NOT NULL                 -- ISO-8601 UTC
);
```

---

## Disable / uninstall

**Disable hook for the current session only:**

```bash
# zsh
add-zsh-hook -d preexec _tdb_preexec
add-zsh-hook -d precmd  _tdb_precmd
```

**Remove the hook permanently:**

```bash
tdb unsetup           # zsh
tdb unsetup --shell bash
source ~/.zshrc       # or ~/.bashrc
```

**Uninstall the package:**

```bash
pip uninstall terminaldb
```

Your database at `~/.terminaldb/tdb.sqlite` is not touched by uninstall.

---

## Project layout

```
terminalDB/
├── pyproject.toml
├── requirements.txt
├── README.md
├── start-mlx.sh       # launches MLX server (Apple Silicon)
└── terminaldb/
    ├── __init__.py
    ├── cli.py          # Typer CLI — all commands
    ├── db.py           # SQLite persistence layer
    ├── llm.py          # Ollama + MLX via OpenAI-compatible API
    ├── display.py      # ANSI terminal output helpers
    ├── shell/
    │   ├── tdb.zsh     # zsh preexec/precmd hook
    │   └── tdb.bash    # bash PROMPT_COMMAND hook
    └── web/
        ├── server.py           # Flask application factory
        ├── templates/
        │   └── index.html
        └── static/
            ├── style.css
            └── app.js
```

---

## Security

- The web dashboard binds to `127.0.0.1` only — not reachable from the network.
- CORS is restricted to `http://localhost:7777`.
- All SQL queries use parameterized statements — no string interpolation.
- Command input is sanitized: ANSI escape codes are stripped, length is capped at 500 characters.
- No data is sent to any external service. All LLM calls go to your local Ollama or MLX server.

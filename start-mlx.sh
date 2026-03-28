#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# start-mlx.sh — Launch MLX LLM server for terminalDB
# ─────────────────────────────────────────────────────────────────────────────
set -e

MODEL="${TDB_MLX_MODEL:-mlx-community/Llama-3.2-3B-Instruct-4bit}"
HOST="${TDB_MLX_HOST:-127.0.0.1}"
PORT="${TDB_MLX_PORT:-8080}"

echo ""
echo "  terminalDB — MLX server"
echo "  model : $MODEL"
echo "  url   : http://$HOST:$PORT"
echo ""
echo "  Set these in your shell before running 'tdb':"
echo "    export TDB_LLM=mlx"
echo "    export TDB_MLX_HOST=http://$HOST:$PORT"
echo ""
echo "  Press Ctrl+C to stop."
echo ""

# Check mlx_lm is available
if ! command -v mlx_lm.server &>/dev/null; then
  echo "ERROR: mlx_lm not found. Install with: pip install mlx-lm"
  exit 1
fi

mlx_lm.server \
  --model "$MODEL" \
  --host "$HOST" \
  --port "$PORT"

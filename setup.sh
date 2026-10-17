#!/usr/bin/env bash
# Run once at the start of each agent session, from the repo root.
set -e
export TETEA_ROOT="$(cd "$(dirname "$0")" && pwd)"
pip install -q -r "$TETEA_ROOT/requirements.txt" 2>/dev/null || pip install -q --break-system-packages -r "$TETEA_ROOT/requirements.txt"
if ! command -v tectonic >/dev/null 2>&1; then
  mkdir -p "$HOME/.local/bin"
  (cd "$HOME/.local/bin" && curl --proto '=https' --tlsv1.2 -fsSL https://drop-sh.fullyjustified.net | sh)
fi
export PATH="$HOME/.local/bin:$PATH"
echo "TETEA_ROOT=$TETEA_ROOT"
tectonic --version || echo "WARNING: Tectonic unavailable - chemistry will stay unresolved_region"

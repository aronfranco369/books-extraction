#!/usr/bin/env bash
# Fast session setup. Run from the repo root:  source ./setup.sh [--chem]
#   --chem  also install Tectonic (only needed for drawn chemical structures)
export TETEA_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
export PATH="$HOME/.local/bin:$PATH"
if python3 -c "import pymupdf, PIL" 2>/dev/null; then
  echo "python deps: already present"
else
  pip install -q --disable-pip-version-check -r "$TETEA_ROOT/requirements.txt" 2>/dev/null \
  || pip install -q --disable-pip-version-check --break-system-packages -r "$TETEA_ROOT/requirements.txt"
fi
if [ "$1" = "--chem" ] && ! command -v tectonic >/dev/null 2>&1; then
  mkdir -p "$HOME/.local/bin" && (cd "$HOME/.local/bin" && curl --proto '=https' --tlsv1.2 -fsSL https://drop-sh.fullyjustified.net | sh)
fi
echo "TETEA_ROOT=$TETEA_ROOT  tectonic: $(command -v tectonic >/dev/null && echo yes || echo 'not installed (use --chem if needed)')"

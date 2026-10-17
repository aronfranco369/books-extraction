#!/usr/bin/env bash
# Fetch only what one subject needs (no other PDFs). Usage:
#   curl -fsSL https://raw.githubusercontent.com/aronfranco369/books-extraction/main/get.sh | bash -s csee physics
set -e; LEVEL="$1"; SUBJECT="$2"; DIR="${3:-books-extraction}"
git clone -q --depth 1 --filter=blob:none --sparse https://github.com/aronfranco369/books-extraction "$DIR"
cd "$DIR"
git sparse-checkout set skills tools books2json assets tie/output "tie/books/$LEVEL/$SUBJECT"
echo "ready: $(pwd) (only tie/books/$LEVEL/$SUBJECT downloaded)"

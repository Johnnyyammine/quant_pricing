#!/bin/bash
# macOS launcher: double-click in Finder. Builds if needed, starts Quant Pricer, opens the browser.
cd "$(dirname "$0")" || exit 1
fail() { echo "$1"; read -r -p "Press Enter to close…"; exit 1; }
command -v uv >/dev/null 2>&1 || fail "uv is required: brew install uv  (or https://docs.astral.sh/uv/)"
command -v npm >/dev/null 2>&1 || fail "Node.js 20+ is required: brew install node  (or https://nodejs.org/)"
uv run python scripts/launch.py "$@" || fail "Quant Pricer exited with an error."

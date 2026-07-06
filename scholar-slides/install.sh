#!/usr/bin/env bash
# scholar-slides installer — provisions the Python + Node toolchains and the Chromium binary the
# render/QA/export stages need. Verified on a clean machine (fresh venv + npm install).
set -euo pipefail
cd "$(dirname "$0")"

echo "==> scholar-slides install"

# --- prerequisites ---------------------------------------------------------
command -v python3 >/dev/null || { echo "ERROR: python3 not found (need 3.11+)"; exit 1; }
command -v node    >/dev/null || { echo "ERROR: node not found (need 18+)"; exit 1; }
command -v npm     >/dev/null || { echo "ERROR: npm not found"; exit 1; }

# --- Python side (ingestion, figures, charts, PPTX parity) ------------------
echo "==> creating .venv and installing Python deps"
python3 -m venv .venv
./.venv/bin/pip install -q --upgrade pip
./.venv/bin/pip install -q -r requirements.txt

# --- Node side (build, render, QA, PPTX export) -----------------------------
echo "==> installing Node deps"
npm install --silent

echo "==> installing the Chromium binary Playwright needs (render / QA / equation export)"
npx --yes playwright install chromium

# --- fonts -----------------------------------------------------------------
# Latin + math ship with the deck (Georgia/KaTeX). CJK relies on a system font: macOS and Windows
# have PingFang/Songti/YaHei out of the box; a headless Linux box needs Noto CJK installed once.
if [[ "$(uname)" == "Linux" ]] && ! fc-list 2>/dev/null | grep -qi "Noto Sans CJK\|Source Han"; then
  echo "NOTE: no CJK font detected. For Chinese decks on Linux, install one, e.g.:"
  echo "        sudo apt-get install -y fonts-noto-cjk        # Debian/Ubuntu"
  echo "        sudo dnf install -y google-noto-sans-cjk-fonts # Fedora"
fi

# --- smoke check -----------------------------------------------------------
echo "==> verifying the install (test suites)"
./.venv/bin/python -m pytest -q -p no:cacheprovider >/dev/null && echo "  python tests OK"
npm test >/dev/null 2>&1 && echo "  node tests OK"

echo "==> done. Try:  node scripts/build_deck.mjs out/attention/deck.json && \\"
echo "                node scripts/render_deck.mjs out/attention/deck/deck.html pdf"

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
# The runtime degrades gracefully without Chromium (PPTX still exports; equations just aren't
# rasterized). So a failed browser download must NOT abort the whole install — warn and continue.
if ! npx --yes playwright install chromium; then
  echo "WARN: Chromium download failed (offline / proxy / mirror unreachable)."
  echo "      The rest of the install completed. render / QA screenshots / equation rasterization"
  echo "      stay unavailable until you run 'npx playwright install chromium' on a connected machine."
fi

# --- fonts -----------------------------------------------------------------
# Latin + math ship with the deck (Georgia/KaTeX). CJK relies on a system font: macOS and Windows
# have PingFang/Songti/YaHei out of the box; a headless Linux box needs Noto CJK installed once.
if [[ "$(uname)" == "Linux" ]] && ! fc-list 2>/dev/null | grep -qi "Noto Sans CJK\|Source Han"; then
  echo "NOTE: no CJK font detected. For Chinese decks on Linux, install one, e.g.:"
  echo "        sudo apt-get install -y fonts-noto-cjk        # Debian/Ubuntu"
  echo "        sudo dnf install -y google-noto-sans-cjk-fonts # Fedora"
fi

# --- smoke check -----------------------------------------------------------
# Real self-check: the unit suites must actually pass, and a failure must abort with a clear error
# (never a swallowed failure masquerading as success). Integration tests are excluded — they need
# tests/fixtures/attention.pdf, which is not shipped (a clean clone has no fixture), and they
# self-skip when it is absent. Both unit suites are Chromium-free, so this runs even if the browser
# download above was skipped.
echo "==> verifying the install (unit test suites)"
if ./.venv/bin/python -m pytest -q -m "not integration" -p no:cacheprovider; then
  echo "  python unit tests OK"
else
  echo "ERROR: python unit tests failed (see output above) — install is NOT verified"; exit 1
fi
if npm test; then
  echo "  node tests OK"
else
  echo "ERROR: node tests failed (run 'npm test' to see details) — install is NOT verified"; exit 1
fi

echo "==> done. Try:  node scripts/build_deck.mjs out/attention/deck.json && \\"
echo "                node scripts/render_deck.mjs out/attention/deck/deck.html pdf"

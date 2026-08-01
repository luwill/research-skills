#!/usr/bin/env bash
# lit-search installer — provisions the Python toolchain the retrieval pipeline needs.
# No API key is required to get started: screening can run on the host Claude Code
# via `lit screen --model host`.
set -euo pipefail
cd "$(dirname "$0")"

echo "==> lit-search install"

# --- prerequisites ---------------------------------------------------------
if ! command -v uv >/dev/null; then
  echo "ERROR: uv not found. Install it first:"
  echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"
  echo "  (or: brew install uv)"
  exit 1
fi

# --- Python side -----------------------------------------------------------
echo "==> creating .venv and installing dependencies (needs Python 3.11+)"
uv sync --quiet

# --- smoke check -----------------------------------------------------------
echo "==> verifying the CLI"
uv run lit --help >/dev/null

cat <<'EOF'

==> done.

Next:
  1. Optional credentials — copy .env.example to .env and fill what you need.
     Everything in it is optional; without an LLM key, screen with --model host.
       CONTACT_EMAIL   free, but `lit fulltext` refuses to run without it
       OPENALEX_API    free, raises the daily quota 1,000 -> 10,000 credits

  2. Write a protocol. Start from references/topic-template.yaml; two real ones
     live in examples/ (one biomedical, one pure CS).

  3. Keep run artifacts OUT of this directory — they reach hundreds of MB:
       uv run lit harvest --topic /your/project/topics/x.yaml \
                          --runs-root /your/project/runs --depth quick

  4. See the cost/coverage of each depth tier:
       uv run lit depths
EOF

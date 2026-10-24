#!/usr/bin/env bash
# Mutabiq one-command setup for macOS / Linux.   Run from the project folder:  bash setup.sh
# Needs: Python 3.11+ and Ollama (https://ollama.com/download) installed first.
set -e

echo "1/6 Python environment"
[ -d .venv ] || python3 -m venv .venv
. .venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q || { echo "WeasyPrint failed? Install Pango (brew install pango) or remove it from requirements.txt"; exit 1; }
playwright install chromium

echo "2/6 Open-weight models (Apache-2.0 / MIT)"
ollama pull qwen2.5:7b-instruct
ollama pull bge-m3

echo "3/6 Official law texts";       python scripts/get_laws.py
echo "4/6 Cloud IP ranges";          python scripts/update_cloud_ranges.py
echo "5/6 Search index";             python -m core.rag ingest
echo "6/6 Database + demo engagement"; python scripts/seed.py

cat <<'EOF'

Done. Next:
  MUTABIQ_VERIFY_TOKEN="<token printed above>" python demo_site/app.py
  python scripts/eval_ai.py      # check the model
  python scripts/prewarm.py      # fill the demo cache
  streamlit run app.py
EOF

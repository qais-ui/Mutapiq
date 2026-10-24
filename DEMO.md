# Current no-login legal demo

This is the newer pitch experience. The original `app.py` and Windows
`START_MUTABIQ.bat` still launch the original authenticated application.
For the simplified legal demo, use the instructions below instead.

## Start

With Python 3.11 or later installed, run from this repository's root:

```bash
python -m pip install -r requirements.txt
python run_demo.py
```

Open http://localhost:8501. No login is needed.
The launcher seeds **only a new isolated demo database**, under `db/preview/`,
and runs the fictional website on loopback port 5001. It never resets or opens
the original client database. Stop with Ctrl+C. Ports 5001 and 8501 must be free.

## Optional local chatbot AI

Install Ollama from https://ollama.com, then run:

```bash
ollama pull qwen2.5:3b-instruct
```

The launcher reuses a running Ollama server or starts it if the executable is
available. The model is downloaded separately on each laptop; model blobs and
chat histories are not part of this repository.

The 3B model has a non-OSI Qwen research licence; check its terms for your use.
It was chosen for this CPU-only demo's memory limit, not as a licensing
recommendation. See `OPEN_SOURCE.md` for the original application's alternatives.
Override `MUTABIQ_MODEL` to use another installed, compatible Ollama chat model.
No BGE embedding model or ingestion step is needed for this legal demo.

The review works without Ollama. AI-assisted chat requests show a clear error
if inference is unavailable; the GDPR scope starter uses curated text directly.
Local AI can take up to two minutes, especially when loading a model.

## What the demo does

- 24 curated checks across eight Jordanian business/governance review areas,
  with GDPR conditional on Article 3.
- Public-page reading of the included fictional site only, not pentesting.
- Profile-based applicability questions, source links, guided evidence answers,
  session-only report state and HTML export.
- English/Arabic chatbot with current-report context. Local AI selects checklist
  IDs; the application presents curated material rather than generated legal
  assertions. Chat does not modify the review.

This is not every law, a professionally validated legal opinion, or a compliance
certification. Public wording and self-reported answers are not verified
compliance. Linked authority directories are not live-verified statutory texts.
Do not enter confidential or personal data.

## Checks

```bash
python -m unittest discover -s tests -p "test_legal*.py" -v
```

Never commit databases, encryption keys, ownership tokens, AI caches, model
downloads, local environments, or private client data. `.gitignore` excludes
the normal runtime locations.

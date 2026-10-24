# Mutabiq · مطابق

Compliance map for Jordanian companies: which rules apply (PDPL, NCSC framework, and GDPR / ISO 27001
when expanding to Europe), a passive scan of the company's own website and infrastructure, and
cited explanations in Arabic or English for the owner, the developer, or the lawyer.
No scan runs without a signed engagement, a domain in scope, and proof of domain ownership.

## Run it (10 minutes)

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium                            # optional, real-browser cookie check

python scripts/seed.py                                 # creates db + demo engagement, prints the ownership token
python -m core.rag ingest                              # builds the search index
python demo_site/app.py                                # terminal 1 — the non-compliant demo site on :5001
streamlit run app.py                                   # terminal 2 — the app
```

Logins: `admin / admin123` (Mutabiq team) · `shifa / shifa123` (client). Change them before showing anyone.

**Local demo ownership proof:** the demo site serves the token from the `MUTABIQ_VERIFY_TOKEN` env var.
Start it with the token `seed.py` printed:

```bash
MUTABIQ_VERIFY_TOKEN="mutabiq-verify=ENG-2026-014-xxxx" python demo_site/app.py
```

Then scan `127.0.0.1` in the app. (Rehearsing fully offline: `MUTABIQ_OFFLINE_VERIFY=1 streamlit run app.py`
skips the ownership check — don't use it on stage.)

**AI (open-weight, runs locally — no closed API):** install [Ollama](https://ollama.com), then
`ollama pull qwen2.5:7b-instruct` (Apache-2.0) and `ollama pull bge-m3` (MIT), and re-run
`python -m core.rag ingest` so vectors are built. Weak laptop: `MUTABIQ_MODEL=qwen2.5:1.5b-instruct`
(also Apache-2.0 — do NOT use the 3B, it is under the non-OSI Qwen license). See `OPEN_SOURCE.md`.

The open model does five jobs: company intake from free Arabic/English text, privacy-policy audit,
per-role explanations with citations, "Ask Mutabiq" legal Q&A over the law corpus, and the privacy-notice
draft. The rule engine, not the model, decides what applies. Without Ollama the sidebar turns orange and
templates/keywords are used so the demo can't crash.

License: MIT (see `LICENSE`).

## How it fits together

```
login → engagement (contract) → company profile → gate (5 checks, audit-logged)
      → scanner.py + infra.py → rules.py (findings + which laws apply)
      → rag.py (find the passages) → llm.py (explain per role + language, cite) → report.py (PDF/HTML)
```

| File | What it does | Owner |
|---|---|---|
| `core/schemas.py` | Shared data contract — announce before editing | Shared |
| `core/scanner.py` | HTTPS, headers, TLS, cookies, trackers, consent banner, privacy policy, forms | Security engine |
| `core/infra.py` | DNS, SPF/DMARC, IP owner + country, cloud region, CDN, tracker locations | Security engine |
| `core/rules.py` + `data/rules.yaml` | Which laws apply + findings (deterministic, no AI) | Security engine |
| `data/ref_map.yaml` | Labels + verified article numbers for every reference | Security engine |
| `core/gate.py`, `verify.py`, `engagement.py`, `audit.py`, `db.py` | Contract gate, ownership proof, hash-chained log, encryption | Security engine |
| `core/rag.py` + `data/knowledge/curated.yaml` + `data/laws/` | Hybrid BM25 + bge-m3 retrieval | AI + interface |
| `core/ai.py` | Open-LLM jobs: free-text intake → profile, privacy-policy audit, grounded Q&A | AI + interface |
| `core/llm.py` + `data/glossary.json` | Role/language prompts, citation rules, language guard, cache, template fallback | AI + interface |
| `core/report.py` + `templates/report.html` | Role reports, RTL Arabic, PDF via WeasyPrint | AI + interface |
| `app.py` | Streamlit UI (client + admin views) | AI + interface |
| `demo_site/app.py` | Intentionally non-compliant demo target | Security engine |
| `tests/test_core.py` | Gate, audit tamper detection, rules, AI layer (model mocked) | Shared |

See `HANDOFF.md` for what is done and what is left.

## Team

Built at Hacktoberfest 2026 (Track 3 — Open Governance & Public Impact) by:

- Ahmad Hanafiah
- Qais Rami
- Raghad Imam
- Sara Abozghod


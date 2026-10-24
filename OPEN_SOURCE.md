# Open source & open-weight AI

Mutabiq is MIT-licensed, uses only open-weight models, and calls **no closed AI API**.
All inference runs locally through Ollama — client data never leaves the machine.

## AI models

| Model | Used for | License | Where it runs |
|---|---|---|---|
| Qwen2.5-7B-Instruct (`qwen2.5:7b-instruct`) | Company intake from free text, privacy-policy analysis, finding explanations, legal Q&A, privacy-notice draft | Apache-2.0 | Local, Ollama |
| Qwen2.5-1.5B-Instruct (`qwen2.5:1.5b-instruct`) | Fallback for weak laptops | Apache-2.0 | Local, Ollama |
| BGE-M3 (`bge-m3`) | Multilingual Arabic/English embeddings for retrieval | MIT | Local, Ollama |

**Do not swap in `qwen2.5:3b` or `qwen2.5:72b`** — those two sizes are under the Qwen license, not Apache-2.0.
Check the organisers' list of eligible open-weight models before the demo.

## What the AI does (and what it does not)

| Job | Done by | Why |
|---|---|---|
| Turn "we're a clinic app in Amman with patients in Germany" into a structured company profile | **LLM** (JSON, validated by Pydantic, confirmed by the user) | Owners describe themselves in their own words, in Arabic or English |
| Read the client's privacy policy and list which required elements are missing | **LLM** (JSON with a short quote per element present) | Policies are free text; keyword matching misses most of it |
| Find the law passages behind each finding | **BGE-M3** + BM25 retrieval | Cross-language: an Arabic question finds English GDPR text |
| Explain each finding for owner / developer / lawyer, in Arabic or English, with citations | **LLM**, grounded in retrieved passages only | Same facts, three audiences |
| Answer free questions ("do we need a DPO?") with citations | **LLM** + RAG | Legal Q&A without a consultant |
| Decide whether a law applies or a finding exists | **Rule engine, not the LLM** | Deterministic, explainable, cannot hallucinate a violation |

If Ollama is down, the app shows an orange "AI offline" badge and falls back to templates so a demo never crashes —
but the intended mode, and the one shown to judges, is the local open model.

## Libraries

Streamlit (Apache-2.0), Pydantic (MIT), Requests (Apache-2.0), dnspython (ISC), ipwhois (BSD-2), Beautiful Soup (MIT),
PyYAML (MIT), Jinja2 (BSD-3), rank_bm25 (Apache-2.0), cryptography (Apache-2.0/BSD), bcrypt (Apache-2.0),
Flask (BSD-3), Gunicorn (MIT), Playwright (Apache-2.0), WeasyPrint (BSD-3), Ollama (MIT).
PyMuPDF is AGPL-3.0 — fine for an open-source project; if you ever relicense, replace it with `pypdf` (BSD).

## Content

- `data/knowledge/curated.yaml` — written by us, MIT.
- `data/laws/` — official legal texts are public; they are downloaded by each user, not redistributed in the repo.
- ISO/IEC 27001 — only control IDs and titles are used; the standard text is copyrighted and is not included.

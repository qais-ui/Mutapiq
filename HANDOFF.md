# Where the build stands — 2026-10-24

All code is written. What's left needs your laptop: internet (models, law texts, deployment) and a GPU (the model).
Tests: `python -m pytest -q` → 10 passed. The UI flow was tested end to end with the model mocked,
because the build sandbox can't download Ollama or models. **Real Qwen output has not been seen yet — step 3 below.**

## Run it on Windows (one double-click)

1. Unzip `mutabiq.zip` anywhere (for example the Desktop).
2. Double-click **`START_MUTABIQ.bat`**.
   - No Python or Ollama yet? It installs them with winget, then asks you to close the window and double-click again.
   - First full run downloads the AI models and law texts: 15–30 minutes. Later runs start in seconds.
3. Your browser opens **http://localhost:8501**. Log in `shifa / shifa123` and scan `127.0.0.1`.
4. To stop: close the two black windows titled "Mutabiq".

Before the pitch (optional but recommended), in the project folder run:
`.venv\Scripts\python.exe scripts\eval_ai.py` (checks the model) then `.venv\Scripts\python.exe scripts\prewarm.py`
(caches every AI answer the demo needs). Then record a backup video.

Optional — deploy the demo site to Render (region Frankfurt, start command `gunicorn demo_site.app:app`, env
`MUTABIQ_VERIFY_TOKEN`), then `MUTABIQ_DEMO_DOMAIN=<your>.onrender.com python scripts/seed.py`.
The local demo on 127.0.0.1 is enough if time is short. Fill the deck placeholders (team names, GitHub, partner).

If `get_laws.py` reports FAIL for a file, download it in the browser to `data/laws/` with the printed name
and run `python -m core.rag ingest` again. The app works without them (curated notes cover every topic).

## What was verified (and against what)

| Item | Status | Source |
|---|---|---|
| PDPL article numbers in `data/ref_map.yaml` | Verified | Official English translation, MoDEE |
| DPO triggers (Art. 11(A)(1)–(5)), sensitive-data list (Art. 2), breach 24h/72h (Art. 20), fines (Art. 21–22) | Built into rules | Same |
| Arabic legal terms in `data/glossary.json` (المسؤول = controller, المراقب = DPO) | Verified | Arabic text, jordan-lawyer.com (re-check vs Official Gazette) |
| NCSC critical-sector list | **Not public** — app asks the user; likely sectors show "confirm with NCSC" | Al Mamlaka, 28 Jun & 8 Sep 2026 |
| NCSC control numbers | **Not public** — shown as "to be confirmed" | — |
| Qwen2.5-7B Apache-2.0 · BGE-M3 MIT · Qwen2.5-3B/72B Qwen license | Verified | Ollama model pages |

## Demo script (≈3 min, matches slide 4)

0. Sidebar badge: Qwen2.5-7B (Apache-2.0) + BGE-M3 (MIT), local, no cloud API.
1. Log in `shifa / shifa123`. Scan a bank's domain → **blocked**. Log in as `admin` → audit entry → "Verify audit chain".
2. Back as `shifa`: paste the dialect description from `scripts/prewarm.py` → **Fill the profile with AI** → save.
3. Scan `127.0.0.1` (or the Render domain) → gate passes → metrics, framework cards, findings tabs.
4. Same finding as **owner / Arabic**, then **developer / English**.
5. Privacy-policy check panel. Ask exactly: **هل يلزمنا تعيين مراقب لحماية البيانات؟** (pre-warmed).
6. Correct hosting country to `JO` → the PDPL transfer finding disappears and the GDPR one appears
   (EU patients' data now sits outside the EU). That's the "both directions" point on slide 8.
7. Legal role → draft privacy notice → download the Arabic report.

## Known limits (say them if judges ask)

- Hosting country behind a CDN can't be detected; the app says "origin hidden" and asks the user.
- Consent-banner detection is heuristic.
- NCSC controls aren't public, so NCSC findings cite the framework's scope, not control numbers.
- Guidance, not legal advice — every report says so.

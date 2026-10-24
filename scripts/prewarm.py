"""Pre-compute every AI answer the live demo will need, so nothing waits on the model on stage.

    python scripts/prewarm.py                         # local demo site at http://127.0.0.1:5001
    python scripts/prewarm.py shifa-demo.onrender.com # deployed demo site

Uses the same inputs the demo script uses (dialect description → profile, scan, policy audit,
3 roles × 2 languages, two Ask questions, privacy-notice drafts). Answers land in data/cache/.
Run it again if you change a prompt, the model, or the demo site.
"""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.ai import analyze_privacy_policy, ask, profile_from_text  # noqa: E402
from core.infra import map_infra  # noqa: E402
from core.llm import MODEL, draft_privacy_notice, explain, ollama_status  # noqa: E402
from core.rules import evaluate  # noqa: E402
from core.scanner import scan  # noqa: E402


DEMO_TEXT = ("احنا تطبيق حجز عيادات في عمّان، ملفات المرضى على AWS فرانكفورت، وفي مرضى ساكنين بألمانيا، "
             "وبدنا نتوسع لأوروبا السنة الجاية")
QUESTIONS = [("هل يلزمنا تعيين مراقب لحماية البيانات؟", "ar"), ("How fast must we report a data breach?", "en")]

if not ollama_status()["llm_ready"]:
    sys.exit(f"Ollama/{MODEL} not ready — start Ollama and pull the model first.")

args = [a for a in sys.argv[1:] if not a.startswith("--")]
target = args[0] if args else "127.0.0.1"
local = target in ("127.0.0.1", "localhost")
t0 = time.time()

prof, meta = profile_from_text(DEMO_TEXT, target, "Shifa Health LLC")
assert prof, f"intake failed: {meta}"
print("profile:", prof.model_dump())

s = scan(target, base_url="http://127.0.0.1:5001" if local else None)
if not local:
    s.infra.update(map_infra(target, s.headers.get("raw"), list(s.infra.get("trackers", {}).keys())))
if s.privacy_policy.get("found"):
    s.privacy_policy["analysis"] = analyze_privacy_policy(s.privacy_policy.get("text_excerpt", ""))
    print("policy missing:", s.privacy_policy["analysis"]["missing"])

# --quick (default): the demo path only — critical/high findings for owner/Arabic and developer/English (~6-10 min
# on a laptop GPU). --full: every finding, every role and language, before and after the correction (~1 h).
FULL = "--full" in sys.argv
combos = [(r, l) for r in ("owner", "developer", "legal") for l in ("ar", "en")] if FULL else [("owner", "ar"), ("developer", "en")]
for confirmed in (({}, {"hosting_country": "JO"}) if FULL else ({},)):
    report = evaluate(prof, s, confirmed)
    todo = report.findings if FULL else [f for f in report.findings if f.severity in ("critical", "high")]
    for role, lang in combos:
        for f in todo:
            t = time.time()
            ex = explain(f, role, lang)
            print(f"  {role:9s} {lang} {f.id:28s} {ex.get('generated_by')}  {time.time() - t:.0f}s", flush=True)
for lang in (("ar", "en") if FULL else ("ar",)):
    draft_privacy_notice(prof, report.findings, lang)
for q, lang in QUESTIONS:
    for laws in (["PDPL", "NCSC", "CYBERSECURITY_LAW", "GDPR", "EPRIVACY", "ISO"], ["PDPL", "NCSC", "CYBERSECURITY_LAW"]):
        ask(q, lang, laws)
print(f"\nDone in {time.time() - t0:.0f}s. Any line above that says 'template' means the model failed for that finding.")

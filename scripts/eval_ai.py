"""Check the open model's 5 jobs on fixed cases. Run on the demo laptop with Ollama up:

    python scripts/eval_ai.py                 # default model (qwen2.5:7b-instruct)
    MUTABIQ_MODEL=qwen2.5:1.5b-instruct python scripts/eval_ai.py

Prints PASS/FAIL per check, the time each job took, and saves every raw answer to
data/cache/eval_<model>.json so you can read what the model actually wrote.
Caching is OFF here so you see real latency.
"""
import json
import os
import sys
import time
from pathlib import Path

os.environ["MUTABIQ_NO_CACHE"] = "1"
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.ai import analyze_privacy_policy, ask, profile_from_text  # noqa: E402
from core.llm import MODEL, _lang_ok, draft_privacy_notice, explain, ollama_status  # noqa: E402
from core.rules import load_rules  # noqa: E402
from core.schemas import CompanyProfile, Finding  # noqa: E402

results, raw = [], {}


def check(job: str, name: str, ok: bool, detail: str = "") -> None:
    results.append((job, name, ok, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  — {detail}" if detail and not ok else ""))


def timed(fn, *a, **kw):
    t = time.time()
    out = fn(*a, **kw)
    return out, time.time() - t


st = ollama_status()
print(f"Model: {MODEL}  Ollama up: {st['up']}  models: {st['models']}")
if not st["llm_ready"]:
    sys.exit(f"Model {MODEL} is not pulled. Run:  ollama pull {MODEL}")

# 1 ─ intake from free text ------------------------------------------------------------------------
print("\n1. Intake from free text")
INTAKE = [
    ("احنا تطبيق حجز عيادات في عمّان، ملفات المرضى على AWS فرانكفورت، وفي مرضى ساكنين بألمانيا، وبدنا نتوسع لأوروبا السنة الجاية",
     {"sector": "health", "data_types": "health", "hosting_country": "DE", "user_countries": "DE", "expanding_to_eu": True}),
    ("We are an e-commerce shop in Irbid selling clothes, we take card payments through a local bank gateway, servers are in Amman, customers only in Jordan.",
     {"sector": "ecommerce", "data_types": "financial", "hosting_country": "JO", "expanding_to_eu": False}),
    ("مدرسة خاصة في الزرقاء عندنا منصة واجبات للطلاب (أعمارهم 6 إلى 15) مستضافة على Google Cloud بلجيكا",
     {"sector": "education", "data_types": "children", "hosting_country": "BE"}),
]
for i, (text, want) in enumerate(INTAKE, 1):
    (prof, meta), secs = timed(profile_from_text, text, "example.jo")
    raw[f"intake_{i}"] = {"profile": prof.model_dump() if prof else None, "meta": meta, "seconds": round(secs, 1)}
    if not prof:
        check("intake", f"case {i} returns a valid profile", False, meta.get("notes", ""))
        continue
    for field, exp in want.items():
        got = getattr(prof, field)
        ok = (exp in got) if isinstance(got, list) else (got == exp)
        check("intake", f"case {i} {field} = {exp}", ok, f"got {got}")
    print(f"        {secs:.1f}s")

# 2 ─ privacy-policy audit (the demo site's deliberately incomplete policy) -------------------------
print("\n2. Privacy-policy audit")
sys.path.insert(0, str(ROOT / "demo_site"))
from demo_site.app import PRIVACY  # noqa: E402
from bs4 import BeautifulSoup  # noqa: E402

policy = BeautifulSoup(PRIVACY, "html.parser").get_text(" ", strip=True)
res, secs = timed(analyze_privacy_policy, policy)
raw["policy"] = {**res, "seconds": round(secs, 1)}
check("policy", "answered by the model (not keyword fallback)", res["generated_by"] == MODEL, res["generated_by"])
for k in ["legal_basis", "retention", "international_transfers", "data_subject_rights", "withdraw_consent", "dpo_contact"]:
    check("policy", f"flags missing: {k}", k in res["missing"])
for k in ["data_categories", "purposes", "controller_identity"]:
    check("policy", f"finds present: {k}", k not in res["missing"])
print(f"        {secs:.1f}s")

# 3 ─ explanations: 3 roles × 2 languages --------------------------------------------------------
print("\n3. Explanations")
meta = load_rules()["findings"]["COOKIE_BEFORE_CONSENT"]
f = Finding(id="COOKIE_BEFORE_CONSENT", title=meta["title"], title_ar=meta["title_ar"], severity=meta["severity"],
            jurisdictions=meta["jurisdictions"], refs=meta["refs"], evidence={"tracking_cookies": ["_ga", "_fbp"]})
for role in ("owner", "developer", "legal"):
    for lang in ("ar", "en"):
        ex, secs = timed(explain, f, role, lang, False)
        raw[f"explain_{role}_{lang}"] = {**ex, "seconds": round(secs, 1)}
        text = " ".join([ex["summary"], ex["why_it_matters"], *map(str, ex["what_to_do"])])
        check("explain", f"{role}/{lang} from the model", ex.get("generated_by") == MODEL, ex.get("generated_by"))
        check("explain", f"{role}/{lang} right language", _lang_ok(text, lang))
        check("explain", f"{role}/{lang} cites only allowed refs", set(ex["citations"]) <= set(f.refs))
        print(f"        {secs:.1f}s")

# 4 ─ Ask Mutabiq ------------------------------------------------------------------------------------
print("\n4. Ask Mutabiq (grounded Q&A)")
for i, (q, lang, must) in enumerate([
        ("هل يلزمنا تعيين مراقب لحماية البيانات إذا كنا نعالج بيانات صحية؟", "ar", ["11", "المراقب"]),
        ("How fast must we report a data breach in Jordan?", "en", ["24", "72"]),
        ("Can we host Jordanian customers' data on AWS Frankfurt?", "en", ["15"])], 1):
    out, secs = timed(ask, q, lang, ["PDPL", "GDPR"])
    raw[f"ask_{i}"] = {**out, "seconds": round(secs, 1)}
    check("ask", f"q{i} answered by the model", out["generated_by"] == MODEL)
    check("ask", f"q{i} cites a source [n]", "[" in out["answer"])
    check("ask", f"q{i} mentions {must}", all(m in out["answer"] for m in must), out["answer"][:160])
    print(f"        {secs:.1f}s")

# 5 ─ privacy-notice draft ----------------------------------------------------------------------------
print("\n5. Privacy-notice draft")
prof = CompanyProfile(name="Shifa Health", domain="example.jo", sector="health", data_types=["basic", "health"])
for lang in ("ar", "en"):
    text, secs = timed(draft_privacy_notice, prof, [], lang)
    raw[f"draft_{lang}"] = {"text": text, "seconds": round(secs, 1)}
    check("draft", f"{lang} right language", _lang_ok(text, lang))
    check("draft", f"{lang} marked as draft for lawyer review",
          any(w in text.lower() for w in ("draft", "lawyer", "مسودة", "محام")))
    print(f"        {secs:.1f}s")

out = ROOT / "data" / "cache" / f"eval_{MODEL.replace(':', '_')}.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(raw, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
passed = sum(r[2] for r in results)
print(f"\n{passed}/{len(results)} checks passed · raw answers: {out}")
for job in dict.fromkeys(r[0] for r in results):
    rs = [r for r in results if r[0] == job]
    print(f"  {job:8s} {sum(r[2] for r in rs)}/{len(rs)}")

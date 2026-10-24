"""Explanation layer — owned by the teammate (AI + interface).

The LLM never decides whether something is a violation (the rule engine does). It only explains
a finding for one role in one language, using ONLY the retrieved passages, and cites refs.
If Ollama is down or the answer fails validation, a deterministic template answer is used,
so the demo never breaks.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import requests

from core.rag import context_for_finding
from core.rules import load_refs, load_rules, ref_label
from core.schemas import Finding

ROOT = Path(__file__).resolve().parent.parent
OLLAMA = os.environ.get("OLLAMA_URL", "http://localhost:11434")
MODEL = os.environ.get("MUTABIQ_MODEL", "qwen2.5:7b-instruct")
NUM_CTX = int(os.environ.get("MUTABIQ_NUM_CTX", "4096"))   # smaller context = more layers fit on a 4 GB GPU
CACHE = ROOT / "data" / "cache" / "explanations.json"
GLOSSARY = json.loads((ROOT / "data" / "glossary.json").read_text(encoding="utf-8"))["terms"]

ROLE_PROMPTS = {
    "owner": ("You explain compliance findings to a busy business owner with no technical or legal background. "
              "Use plain words, no jargon. Explain the business risk, how hard the fix is, and the priority."),
    "developer": ("You explain compliance findings to a software developer. Give exact technical fixes with "
                  "config or code where useful, and name the control the fix satisfies."),
    "legal": ("You explain compliance findings to a lawyer or Data Protection Officer. State the obligation, "
              "the legal basis, and which documents or records the company must prepare. Be precise."),
}
LANG_RULES = {
    "ar": ("اكتب جميع القيم النصية في JSON باللغة العربية الفصحى فقط. أبقِ أسماء التقنيات والترويسات والكود "
           "بالإنجليزية (مثل HSTS وTLS وCSP). استخدم المصطلحات التالية حرفياً كما هي:\n{glossary}"),
    "en": "Write every text value in the JSON in English only. When citing the Jordanian PDPL you may add the Arabic term in brackets.",
}
SYSTEM_RULES = """Rules you must follow:
1. Use ONLY the facts in the SOURCES and the FINDING below. If something is not in them, do not say it.
2. Never invent article numbers. Cite only with the citation keys given in ALLOWED_CITATIONS.
3. Do not say the company is definitely breaking the law; say what the finding means and what to do.
4. Answer with ONLY a JSON object, no markdown, with exactly these keys:
   {"summary": str, "why_it_matters": str, "what_to_do": [str, ...], "citations": [str, ...]}
   what_to_do has 2 to 4 short items. citations is a subset of ALLOWED_CITATIONS."""


def _cache() -> dict:
    return json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}


def _stable(obj):
    """Evidence without volatile values (resolved IPs change between runs and would break the demo cache)."""
    if isinstance(obj, dict):
        return {k: _stable(v) for k, v in obj.items() if k not in ("ip", "ips", "status")}
    if isinstance(obj, list):
        return [_stable(v) for v in obj]
    return obj


def _cache_key(f: Finding, role: str, lang: str) -> str:
    raw = json.dumps([f.id, role, lang, _stable(f.evidence), MODEL], sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _lang_ok(text: str, lang: str) -> bool:
    arabic = sum(1 for ch in text if "؀" <= ch <= "ۿ")
    letters = sum(1 for ch in text if ch.isalpha()) or 1
    return (arabic / letters > 0.5) if lang == "ar" else (arabic / letters < 0.05)


def _build_prompt(f: Finding, role: str, lang: str, ctx: list[dict]) -> list[dict]:
    glossary = "\n".join(f"- {en} = {ar}" for en, ar in GLOSSARY.items())
    sources = "\n\n".join(f"[{c['for_ref']}] ({c['source']}{', ' + c['article'] if c.get('article') else ''})\n{c['text']}"
                          for c in ctx)
    finding = {"title": f.title, "severity": f.severity, "evidence": f.evidence, "fix_effort": f.fix_effort,
               "jurisdictions": f.jurisdictions}
    system = "\n\n".join([ROLE_PROMPTS[role], LANG_RULES[lang].format(glossary=glossary), SYSTEM_RULES])
    user = (f"ALLOWED_CITATIONS: {json.dumps(f.refs)}\n\nFINDING:\n{json.dumps(finding, ensure_ascii=False, default=str)}"
            f"\n\nSOURCES:\n{sources}")
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _call_ollama(messages: list[dict]) -> dict | None:
    try:
        r = requests.post(f"{OLLAMA}/api/chat", timeout=300, json={
            "model": MODEL, "messages": messages, "stream": False, "format": "json",
            "keep_alive": "3h",                       # don't unload between demo steps (reload costs ~1 min)
            "options": {"temperature": 0.2, "num_ctx": NUM_CTX}})
        r.raise_for_status()
        return json.loads(r.json()["message"]["content"])
    except Exception:  # noqa: BLE001
        return None


def _valid(ans: dict | None, f: Finding, lang: str) -> bool:
    if not isinstance(ans, dict) or not {"summary", "why_it_matters", "what_to_do", "citations"} <= ans.keys():
        return False
    if not isinstance(ans["what_to_do"], list) or not ans["what_to_do"]:
        return False
    ans["citations"] = [c for c in ans.get("citations", []) if c in f.refs] or f.refs
    text = " ".join([ans["summary"], ans["why_it_matters"], *map(str, ans["what_to_do"])])
    return _lang_ok(text, lang)


def template_answer(f: Finding, role: str, lang: str, ctx: list[dict]) -> dict:
    """Deterministic fallback built from rules.yaml + the best retrieved passage."""
    ar = lang == "ar"
    plain = next((c["text"] for c in ctx if c.get("lang") == lang and c.get("audience") in ("plain", "legal")), None)
    tech = next((c["text"] for c in ctx if c.get("audience") == "technical"), None)
    effort = {"low": ("منخفض", "low"), "medium": ("متوسط", "medium"), "high": ("مرتفع", "high")}[f.fix_effort]
    if ar:
        todo = ["عالجوا هذه الملاحظة بالأولوية: " + {"critical": "فورية", "high": "عالية", "medium": "متوسطة", "low": "منخفضة"}[f.severity],
                "اطلبوا من فريق تقنية المعلومات تطبيق الإصلاح ثم أعيدوا الفحص",
                "وثّقوا الإجراء المتخذ ضمن سجلات الامتثال"]
    else:
        todo = [f"Treat this as {f.severity} priority (fix effort: {effort[1]})",
                tech or "Ask your IT team to apply the fix, then re-run the scan",
                "Record the fix in your compliance records"]
    return {
        "summary": f.title_ar if ar and f.title_ar else f.title,
        "why_it_matters": plain or (("هذه الملاحظة مرتبطة بالمتطلبات التالية: " if ar else "This finding relates to: ")
                                    + "؛ ".join(ref_label(r, lang) for r in f.refs)),
        "what_to_do": todo,
        "citations": f.refs,
        "generated_by": "template",
    }


def explain(f: Finding, role: str = "owner", lang: str = "en", use_cache: bool = True, use_llm: bool = True) -> dict:
    use_cache = use_cache and os.environ.get("MUTABIQ_NO_CACHE") != "1"
    key = _cache_key(f, role, lang)
    cache = _cache() if use_cache else {}
    if key in cache:
        return {**cache[key], "cached": True}
    ctx = context_for_finding(f, role, lang)
    ans = None
    if use_llm:
        msgs = _build_prompt(f, role, lang, ctx)
        for _ in range(2):                          # one retry if wrong language / bad JSON
            ans = _call_ollama(msgs)
            if _valid(ans, f, lang):
                ans["generated_by"] = MODEL
                break
            ans = None
    ans = ans or template_answer(f, role, lang, ctx)
    ans["citation_labels"] = [ref_label(r, lang) for r in ans["citations"]]
    ans["sources"] = [{"ref": c["for_ref"], "source": c["source"], "article": c.get("article"),
                       "excerpt": c["text"][:400]} for c in ctx]
    if use_cache and ans.get("generated_by") != "template":
        cache[key] = ans
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    return ans


def cached_explanation(f: Finding, role: str, lang: str) -> dict | None:
    """An LLM explanation already in the cache (from prewarm or an earlier click), else None. Never calls the model."""
    hit = _cache().get(_cache_key(f, role, lang))
    if not hit:
        return None
    hit = {**hit, "cached": True}
    hit.setdefault("citation_labels", [ref_label(r, lang) for r in hit.get("citations", f.refs)])
    return hit


def warm_up() -> bool:
    """Load the model into memory so the first real question isn't slow."""
    try:
        requests.post(f"{OLLAMA}/api/generate", timeout=300,
                      json={"model": MODEL, "prompt": "", "keep_alive": "3h"})
        return True
    except Exception:  # noqa: BLE001
        return False


def ollama_status() -> dict:
    try:
        tags = requests.get(f"{OLLAMA}/api/tags", timeout=3).json()
        names = [m["name"] for m in tags.get("models", [])]
        return {"up": True, "models": names, "llm_ready": any(MODEL.split(":")[0] in n for n in names),
                "embed_ready": any("bge-m3" in n for n in names)}
    except Exception:  # noqa: BLE001
        return {"up": False, "models": [], "llm_ready": False, "embed_ready": False}


def draft_privacy_notice(profile, findings: list[Finding], lang: str = "ar") -> str:
    """Generates a DRAFT privacy notice for the client to give to a lawyer. Template fallback if no LLM."""
    facts = {"company": profile.name, "domain": profile.domain, "data_types": profile.data_types,
             "user_countries": profile.user_countries,
             "trackers": next((x.evidence.get("trackers") for x in findings if x.id == "THIRD_PARTY_TRACKERS"), {}),
             "hosting_country": next((x.evidence.get("hosting_country") for x in findings if x.id == "DATA_HOSTED_OUTSIDE_JO"), "JO")}
    prompt = [{"role": "system", "content": (
        "Write a short DRAFT website privacy notice in " + ("Modern Standard Arabic" if lang == "ar" else "English") +
        " using ONLY these facts. Sections: who we are, what data we collect, why, who receives it, transfers outside "
        "Jordan, how long we keep it, your rights, contact. Mark unknown details as [to be completed]. "
        "Start with a line saying it is a draft that must be reviewed by a lawyer. Answer as JSON {\"text\": str}.")},
        {"role": "user", "content": json.dumps(facts, ensure_ascii=False)}]
    key = "draft:" + hashlib.sha256(json.dumps([MODEL, lang, facts], sort_keys=True, ensure_ascii=False,
                                                  default=str).encode()).hexdigest()[:16]
    use_cache = os.environ.get("MUTABIQ_NO_CACHE") != "1"
    cache = _cache() if use_cache else {}
    if key in cache:
        return cache[key]
    ans = _call_ollama(prompt)
    if ans and isinstance(ans.get("text"), str) and _lang_ok(ans["text"], lang):
        if use_cache:
            cache[key] = ans["text"]
            CACHE.parent.mkdir(parents=True, exist_ok=True)
            CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
        return ans["text"]
    if lang == "ar":
        return (f"مسودة — يجب مراجعتها من قبل محامٍ قبل النشر.\n\nإشعار الخصوصية لشركة {profile.name}\n\n"
                f"البيانات التي نجمعها: {', '.join(profile.data_types) or '[يُستكمل]'}\n"
                f"الغاية من المعالجة: [يُستكمل]\nالجهات المستلمة: {', '.join(facts['trackers'].values()) or '[يُستكمل]'}\n"
                f"نقل البيانات خارج المملكة: {facts['hosting_country']}\nمدة الاحتفاظ: [يُستكمل]\n"
                "حقوقكم: الاطلاع والتصحيح والمحو والاعتراض وسحب الموافقة.\nللتواصل: [يُستكمل]")
    return (f"DRAFT — must be reviewed by a lawyer before publishing.\n\nPrivacy notice — {profile.name}\n\n"
            f"Data we collect: {', '.join(profile.data_types) or '[to be completed]'}\nWhy: [to be completed]\n"
            f"Who receives it: {', '.join(facts['trackers'].values()) or '[to be completed]'}\n"
            f"Transfers outside Jordan: {facts['hosting_country']}\nRetention: [to be completed]\n"
            "Your rights: access, correction, erasure, objection, withdrawing consent.\nContact: [to be completed]")


if __name__ == "__main__":
    print(json.dumps(ollama_status(), indent=2))
    meta = load_rules()["findings"]["COOKIE_BEFORE_CONSENT"]
    demo = Finding(id="COOKIE_BEFORE_CONSENT", title=meta["title"], title_ar=meta["title_ar"], severity=meta["severity"],
                   jurisdictions=meta["jurisdictions"], refs=meta["refs"], evidence={"tracking_cookies": ["_ga"]})
    print(json.dumps(explain(demo, "owner", "ar", use_cache=False), ensure_ascii=False, indent=2)[:1500])
    _ = load_refs

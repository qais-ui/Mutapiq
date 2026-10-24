"""Passive website scanner — owned by the security engine (Ahmad).

Only reads what any visitor's browser already receives. No fuzzing, no brute force,
no exploitation. It must only ever be called through gate.authorize_scan().
"""
from __future__ import annotations

import datetime as dt
import re
import socket
import ssl
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from core.schemas import ScanResult

UA = "Mutabiq-ComplianceScanner/0.1 (+authorized engagement; passive)"
TIMEOUT = 10

TRACKER_DOMAINS = {
    "google-analytics.com": "Google Analytics", "googletagmanager.com": "Google Tag Manager",
    "doubleclick.net": "Google Ads", "googleadservices.com": "Google Ads",
    "connect.facebook.net": "Meta Pixel", "facebook.com": "Meta", "hotjar.com": "Hotjar",
    "clarity.ms": "Microsoft Clarity", "analytics.tiktok.com": "TikTok Pixel",
    "sc-static.net": "Snap Pixel", "snap.licdn.com": "LinkedIn Insight", "ads-twitter.com": "X Ads",
    "static.ads-twitter.com": "X Ads", "mixpanel.com": "Mixpanel", "segment.com": "Segment",
    "yandex.ru": "Yandex Metrica", "mc.yandex.ru": "Yandex Metrica",
}
TRACKING_COOKIE_PATTERNS = [r"^_ga", r"^_gid$", r"^_gat", r"^_gcl", r"^_fbp$", r"^_fbc$", r"^_hj",
                            r"^_clck$", r"^_clsk$", r"^_tt_", r"^_scid", r"^li_", r"^_uet", r"^mp_", r"^ajs_"]
CMP_HINTS = ["cookiebot", "onetrust", "cookieyes", "osano", "iubenda", "klaro", "tarteaucitron",
             "cookieconsent", "cookie-consent", "consent-banner", "termly", "complianz"]
CONSENT_WORDS = ["cookie", "cookies", "consent", "ملفات تعريف الارتباط", "الكوكيز", "موافقة", "نستخدم ملفات"]
PRIVACY_WORDS = ["privacy", "privacy policy", "data protection", "سياسة الخصوصية", "الخصوصية", "حماية البيانات"]
PII_FIELD_HINTS = {"email": "email", "mail": "email", "phone": "phone", "mobile": "phone", "tel": "phone",
                   "name": "name", "national": "national_id", "id_number": "national_id", "passport": "passport",
                   "address": "address", "birth": "birth_date", "dob": "birth_date", "card": "payment_card",
                   "iban": "bank", "password": "password", "رقم": "number", "الاسم": "name", "هاتف": "phone"}

ARABIC_RE = re.compile(r"[؀-ۿ]")


def normalize_target(target: str) -> str:
    target = target.strip().lower()
    if "://" in target:
        target = urlparse(target).hostname or target
    return target.strip("/").split("/")[0]


def _session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = UA
    return s


def check_https(host: str, s: requests.Session) -> dict:
    out = {"https_ok": False, "http_redirects_to_https": None, "final_url": None, "error": None}
    try:
        r = s.get(f"https://{host}", timeout=TIMEOUT, allow_redirects=True)
        out.update(https_ok=True, final_url=r.url, status=r.status_code)
    except requests.exceptions.SSLError as e:
        out["error"] = f"TLS error: {e.__class__.__name__}"
    except requests.RequestException as e:
        out["error"] = f"HTTPS unreachable: {e.__class__.__name__}"
    try:
        r = s.get(f"http://{host}", timeout=TIMEOUT, allow_redirects=True)
        out["http_redirects_to_https"] = r.url.startswith("https://")
        if not out["final_url"]:
            out["final_url"] = r.url
    except requests.RequestException:
        pass
    return out


def check_tls(host: str, port: int = 443) -> dict:
    out: dict = {}
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((host, port), timeout=TIMEOUT) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                out["version"] = ssock.version()
                cert = ssock.getpeercert()
                not_after = dt.datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z")
                out["cert_expires"] = not_after.date().isoformat()
                out["cert_days_left"] = (not_after - dt.datetime.utcnow()).days
                out["issuer"] = dict(x[0] for x in cert.get("issuer", []))
    except Exception as e:  # noqa: BLE001
        out["error"] = f"{e.__class__.__name__}: {e}"
        return out
    # Does the server still ACCEPT legacy TLS? (one handshake each, nothing more)
    out["accepts_legacy"] = []
    for name, ver in (("TLSv1", ssl.TLSVersion.TLSv1), ("TLSv1.1", ssl.TLSVersion.TLSv1_1)):
        try:
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            ctx.set_ciphers("ALL:@SECLEVEL=0")
            ctx.minimum_version = ver
            ctx.maximum_version = ver
            with socket.create_connection((host, port), timeout=5) as sock:
                with ctx.wrap_socket(sock, server_hostname=host):
                    out["accepts_legacy"].append(name)
        except Exception:  # noqa: BLE001 — refusal is the good outcome
            pass
    return out


def analyze_headers(headers: dict) -> dict:
    h = {k.lower(): v for k, v in headers.items()}
    csp = h.get("content-security-policy", "")
    return {
        "hsts": h.get("strict-transport-security"),
        "csp": csp or None,
        "x_frame_options": h.get("x-frame-options"),
        "frame_ancestors": "frame-ancestors" in csp,
        "x_content_type_options": h.get("x-content-type-options"),
        "referrer_policy": h.get("referrer-policy"),
        "server": h.get("server"),
        "x_powered_by": h.get("x-powered-by"),
        "raw": dict(headers),
    }


def _cookie_record(c) -> dict:
    rest = {k.lower(): v for k, v in getattr(c, "_rest", {}).items()}
    name = c.name
    return {
        "name": name,
        "domain": c.domain,
        "secure": bool(c.secure),
        "httponly": "httponly" in rest,
        "samesite": rest.get("samesite"),
        "tracking": any(re.search(p, name) for p in TRACKING_COOKIE_PATTERNS),
    }


def _registrable(host: str) -> str:
    parts = (host or "").lower().split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def parse_html(html: str, base_url: str, host: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    site = _registrable(host)
    scripts, trackers = set(), {}
    for tag in soup.find_all(["script", "img", "iframe"], src=True):
        dom = urlparse(urljoin(base_url, tag["src"])).hostname or ""
        if dom and _registrable(dom) != site:
            scripts.add(dom)
    inline_js = " ".join(s.get_text() for s in soup.find_all("script") if not s.get("src"))
    for dom, label in TRACKER_DOMAINS.items():
        if any(d == dom or d.endswith("." + dom) for d in scripts) or dom in inline_js:
            trackers[dom] = label

    text = soup.get_text(" ", strip=True).lower()
    low_html = html.lower()
    consent_banner = any(h in low_html for h in CMP_HINTS) or (
        any(w in text for w in CONSENT_WORDS) and any(w in text for w in ["accept", "agree", "قبول", "أوافق", "موافق"])
    )

    privacy_link = None
    for a in soup.find_all("a", href=True):
        label = (a.get_text(" ", strip=True) + " " + a["href"]).lower()
        if any(w in label for w in PRIVACY_WORDS):
            privacy_link = urljoin(base_url, a["href"])
            break

    forms = []
    for f in soup.find_all("form"):
        action = urljoin(base_url, f.get("action") or base_url)
        fields = []
        for inp in f.find_all(["input", "textarea", "select"]):
            key = " ".join(filter(None, [inp.get("name"), inp.get("id"), inp.get("type"), inp.get("placeholder")])).lower()
            kind = next((v for k, v in PII_FIELD_HINTS.items() if k in key), None)
            if kind:
                fields.append(kind)
        forms.append({"action": action, "method": (f.get("method") or "get").lower(),
                      "over_http": action.startswith("http://"), "pii_fields": sorted(set(fields))})

    return {"third_party_domains": sorted(scripts), "trackers": trackers, "consent_banner": consent_banner,
            "privacy_link": privacy_link, "forms": forms,
            "page_is_arabic": len(ARABIC_RE.findall(text)) > 50}


def check_privacy_policy(url: str | None, s: requests.Session) -> dict:
    if not url:
        return {"found": False}
    try:
        r = s.get(url, timeout=TIMEOUT)
        soup = BeautifulSoup(r.text, "html.parser")
        text = soup.get_text(" ", strip=True)
        return {"found": r.ok, "url": url, "status": r.status_code,
                "has_arabic": len(ARABIC_RE.findall(text)) > 200,
                "length_chars": len(text), "text_excerpt": text[:6000]}
    except requests.RequestException as e:
        return {"found": False, "url": url, "error": e.__class__.__name__}


def browser_check(url: str) -> dict | None:
    """Optional Playwright pass: what a real browser sets on FIRST load, before any click.
    Returns None if Playwright is not installed — the requests-based results are used instead."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            ctx = browser.new_context(user_agent=UA)
            page = ctx.new_page()
            requested = set()
            page.on("request", lambda req: requested.add(urlparse(req.url).hostname or ""))
            page.goto(url, wait_until="networkidle", timeout=20000)
            cookies = ctx.cookies()
            browser.close()
        return {
            "cookies": [{"name": c["name"], "domain": c["domain"], "secure": c["secure"],
                         "httponly": c["httpOnly"], "samesite": c.get("sameSite"),
                         "tracking": any(re.search(pt, c["name"]) for pt in TRACKING_COOKIE_PATTERNS)}
                        for c in cookies],
            "requested_domains": sorted(d for d in requested if d),
        }
    except Exception as e:  # noqa: BLE001
        return {"error": f"{e.__class__.__name__}: {e}"}


def scan(target: str, use_browser: bool = True, base_url: str | None = None) -> ScanResult:
    """base_url lets you scan a local demo site, e.g. http://127.0.0.1:5001 (TLS checks are skipped then)."""
    host = normalize_target(target)
    s = _session()
    res = ScanResult(target=host)

    if base_url:
        res.https = {"https_ok": base_url.startswith("https"), "http_redirects_to_https": False,
                     "final_url": base_url, "local_test": True}
    else:
        res.https = check_https(host, s)
        res.tls = check_tls(host) if res.https.get("https_ok") else {"error": "no HTTPS"}

    url = res.https.get("final_url") or f"https://{host}"
    res.final_url = url
    try:
        r = s.get(url, timeout=TIMEOUT)
    except requests.RequestException as e:
        res.errors.append(f"Could not load page: {e.__class__.__name__}")
        return res

    res.headers = analyze_headers(r.headers)
    res.cookies = [_cookie_record(c) for c in s.cookies]
    parsed = parse_html(r.text, url, urlparse(url).hostname or host)
    res.third_party_scripts = parsed["third_party_domains"]
    res.consent_banner = parsed["consent_banner"]
    res.forms = parsed["forms"]
    res.privacy_policy = check_privacy_policy(parsed["privacy_link"], s)
    res.privacy_policy["page_is_arabic"] = parsed["page_is_arabic"]
    res.infra["trackers"] = parsed["trackers"]

    if use_browser:
        b = browser_check(url)
        if b and "cookies" in b:
            seen = {c["name"] for c in res.cookies}
            res.cookies += [c for c in b["cookies"] if c["name"] not in seen]
            extra = {d for d in b["requested_domains"] if _registrable(d) != _registrable(host)}
            res.third_party_scripts = sorted(set(res.third_party_scripts) | extra)
            for dom, label in TRACKER_DOMAINS.items():
                if any(d == dom or d.endswith("." + dom) for d in extra):
                    res.infra["trackers"][dom] = label
            res.infra["browser_pass"] = True
        elif b and "error" in b:
            res.errors.append(f"browser pass failed: {b['error']}")
    return res


if __name__ == "__main__":
    import json
    import sys
    out = scan(sys.argv[1], base_url=sys.argv[2] if len(sys.argv) > 2 else None)
    print(json.dumps(out.model_dump(), indent=2, ensure_ascii=False, default=str))

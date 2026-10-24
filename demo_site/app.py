"""Shifa Health — an intentionally NON-COMPLIANT demo site that Mutabiq scans in the pitch.

Deliberate problems: Google Analytics loads on first visit (no consent), an incomplete English-only privacy policy,
no HSTS / CSP / X-Frame-Options, server version leaked, a contact form collecting PII,
a session cookie without HttpOnly/SameSite, and a tracking cookie set immediately.

Local:   python demo_site/app.py            -> http://127.0.0.1:5001
Deploy:  Render web service, region Frankfurt (EU) — this triggers the PDPL transfer finding.
         Start command: gunicorn demo_site.app:app
Only ever scan THIS site in the demo — it is the domain in the Shifa Health engagement.
"""
import os
from pathlib import Path

from flask import Flask, make_response, render_template_string, request

app = Flask(__name__)

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Shifa Health — Book a doctor</title>
<script async src="https://www.googletagmanager.com/gtag/js?id=G-DEMO123"></script>
<script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}
gtag('js', new Date()); gtag('config', 'G-DEMO123');</script>
<script src="https://connect.facebook.net/en_US/fbevents.js"></script>
<style>body{font-family:system-ui;max-width:640px;margin:40px auto;padding:0 16px}
input,textarea{display:block;width:100%;margin:6px 0 14px;padding:8px}</style></head>
<body>
<h1>Shifa Health</h1>
<p>Book an appointment with a doctor in Amman. We keep your medical history so doctors can help you faster.</p>
<h2>Book a visit</h2>
<form action="/book" method="post">
  <label>Full name<input name="full_name"></label>
  <label>Email<input type="email" name="email"></label>
  <label>Mobile<input type="tel" name="mobile"></label>
  <label>National ID number<input name="national_id"></label>
  <label>Symptoms<textarea name="symptoms"></textarea></label>
  <button>Book</button>
</form>
{% if booked %}<p><b>Booked — we'll call you.</b></p>{% endif %}
<footer><a href="/about">About us</a> · <a href="/contact">Contact</a> · <a href="/privacy">Privacy policy</a></footer>
</body></html>"""


@app.after_request
def leak_server(resp):
    resp.headers["Server"] = "nginx/1.18.0"
    resp.headers["X-Powered-By"] = "Flask/2.3.2"
    return resp


@app.route("/")
def home():
    resp = make_response(render_template_string(PAGE, booked=False))
    resp.set_cookie("_ga", "GA1.1.123456789.1729760000")      # tracking cookie before consent
    resp.set_cookie("sessionid", "demo-session-abc123")        # no Secure / HttpOnly / SameSite
    return resp


@app.route("/book", methods=["POST"])
def book():
    _ = request.form  # demo only — nothing is stored
    return render_template_string(PAGE, booked=True)


@app.route("/.well-known/mutabiq.txt")
def mutabiq_token():
    # Ownership proof for Mutabiq. Set MUTABIQ_VERIFY_TOKEN to the value printed by scripts/seed.py.
    # (*.onrender.com DNS can't be edited, so this file method is how the demo proves ownership.)
    token = os.environ.get("MUTABIQ_VERIFY_TOKEN", "")
    default_db = Path(__file__).resolve().parent.parent / "db" / "mutabiq.db"
    saved = Path(os.environ.get("MUTABIQ_DB", str(default_db))).parent / "demo_token.txt"
    if not token and saved.exists():          # local demo: use the token scripts/seed.py saved
        token = saved.read_text(encoding="utf-8").strip()
    return token, 200, {"Content-Type": "text/plain"}


# Deliberately INCOMPLETE and English-only: no legal basis, no retention period, no transfers,
# no DPO, no withdrawal or complaint rights. The open LLM should list exactly these as missing.
PRIVACY = """<!doctype html><html><head><meta charset="utf-8"><title>Privacy policy — Shifa Health</title></head>
<body style="font-family:system-ui;max-width:640px;margin:40px auto;padding:0 16px">
<h1>Privacy policy</h1>
<p>Shifa Health respects your privacy. This page explains how we handle information when you use our booking website.</p>
<h2>Information we collect</h2>
<p>When you book a visit we collect your full name, email address, mobile number, national ID number and the
symptoms you describe. We also collect technical information such as your IP address and browser type.</p>
<h2>How we use it</h2>
<p>We use this information to book your appointment, to remind you about it, and to improve our services.
We may also use it to send you offers from our partner clinics.</p>
<h2>Sharing</h2>
<p>We work with trusted partners who help us run the website and understand how visitors use it.</p>
<h2>Contact</h2>
<p>Questions? Email info@shifa.example.</p>
</body></html>"""


@app.route("/privacy")
def privacy():
    return PRIVACY


@app.route("/about")
def about():
    return "<h1>About Shifa Health</h1><p>A clinic-booking startup in Amman.</p>"


@app.route("/contact")
def contact():
    return "<h1>Contact</h1><p>info@shifa.example</p>"


if __name__ == "__main__":
    app.run(port=5001)

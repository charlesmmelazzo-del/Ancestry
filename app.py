"""
Quesenberry & Harvey Family — Flask sidecar.

Serves the static site from /public and handles two endpoints:

   POST /submit        — three submission modes (person / photo / story-or-correction)
   GET  /submit/thanks — confirmation page (also rendered statically as fallback)
   GET  /admin         — moderation queue (HTTP basic-auth: ADMIN_USER / ADMIN_PASS env vars)
   POST /admin/<id>/<action>  — approve | reject | delete

Submissions are stored as JSON files under SUBMISSIONS_DIR (default /data/submissions).
On Railway, mount a Volume at /data so submissions survive redeploys.

Configure via environment variables:
   ADMIN_USER          (default: admin)
   ADMIN_PASS          (REQUIRED — set on Railway)
   SUBMISSIONS_DIR     (default: /data/submissions)
   PORT                (Railway injects this)
"""

import html
import json
import os
import re
import secrets
import time
import uuid
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path

from flask import (
    Flask, request, send_from_directory, redirect, url_for,
    Response, abort,
)
from jinja2 import Environment, select_autoescape
from werkzeug.utils import secure_filename

# ---- config -----------------------------------------------------------------

APP_ROOT = Path(__file__).parent
PUBLIC_DIR = APP_ROOT / "public"
SUBMISSIONS_DIR = Path(os.environ.get("SUBMISSIONS_DIR", "/data/submissions"))
UPLOADS_DIR = SUBMISSIONS_DIR / "uploads"
ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASS = os.environ.get("ADMIN_PASS")  # REQUIRED for /admin
MAX_UPLOAD_MB = 12
ALLOWED_IMAGE_EXTS = {"jpg", "jpeg", "png", "gif", "webp", "tif", "tiff", "heic"}

# Ensure dirs exist (best effort — may fail if no volume mounted yet)
for d in (SUBMISSIONS_DIR, UPLOADS_DIR):
    try:
        d.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"[warn] could not create {d}: {e}")

app = Flask(__name__, static_folder=None)
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024


# ---- helpers ----------------------------------------------------------------

def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def slugify(s, maxlen=40):
    s = re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-").lower()
    return s[:maxlen] or "submission"


def submission_id(kind, name_hint):
    return f"{int(time.time())}-{kind}-{slugify(name_hint)}-{secrets.token_hex(3)}"


def load_submission(sub_id):
    f = SUBMISSIONS_DIR / f"{sub_id}.json"
    if not f.exists():
        return None
    return json.loads(f.read_text())


def all_submissions(status=None):
    if not SUBMISSIONS_DIR.exists():
        return []
    items = []
    for f in sorted(SUBMISSIONS_DIR.glob("*.json"), key=lambda p: p.name, reverse=True):
        try:
            d = json.loads(f.read_text())
            if status and d.get("status") != status:
                continue
            items.append(d)
        except Exception as e:
            print(f"[warn] bad submission file {f}: {e}")
    return items


def save_submission(data):
    SUBMISSIONS_DIR.mkdir(parents=True, exist_ok=True)
    f = SUBMISSIONS_DIR / f"{data['id']}.json"
    f.write_text(json.dumps(data, indent=2))


def write_upload(file_storage, sub_id):
    """Save an uploaded file to UPLOADS_DIR/{sub_id}-{secure_name}."""
    if not file_storage or not file_storage.filename:
        return None
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    ext = file_storage.filename.rsplit(".", 1)[-1].lower() if "." in file_storage.filename else ""
    if ext not in ALLOWED_IMAGE_EXTS:
        return None
    fname = f"{sub_id}-{secure_filename(file_storage.filename)}"
    file_storage.save(UPLOADS_DIR / fname)
    return fname


def basic_auth_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not ADMIN_PASS:
            return Response(
                "ADMIN_PASS environment variable is not set on the server.\n"
                "Set ADMIN_PASS (and optionally ADMIN_USER) in the Railway Variables tab.\n",
                status=503, mimetype="text/plain")
        auth = request.authorization
        if not auth or auth.username != ADMIN_USER or auth.password != ADMIN_PASS:
            return Response(
                "Authentication required.", status=401,
                headers={"WWW-Authenticate": 'Basic realm="Quesenberry & Harvey Admin"'})
        return fn(*args, **kwargs)
    return wrapper


# ---- static file serving ----------------------------------------------------
# Flask serves /public as the document root, with pretty-URL fallback.

@app.route("/")
def root():
    return send_from_directory(PUBLIC_DIR, "index.html")


@app.route("/<path:path>")
def static_files(path):
    full = PUBLIC_DIR / path
    if full.is_dir():
        idx = full / "index.html"
        if idx.exists():
            return send_from_directory(PUBLIC_DIR, str((Path(path) / "index.html")))
    if full.exists():
        return send_from_directory(PUBLIC_DIR, path)
    # try pretty-URL fallback (path → path.html)
    if not path.endswith(".html"):
        candidate = PUBLIC_DIR / (path + ".html")
        if candidate.exists():
            return send_from_directory(PUBLIC_DIR, path + ".html")
    return abort(404)


# Serve submitted upload images (so admin can preview them, and so that approved
# images can be linked from the live site if Mike wants to embed them directly).
@app.route("/uploads/<path:fname>")
def serve_upload(fname):
    return send_from_directory(UPLOADS_DIR, fname)


# ---- /submit ---------------------------------------------------------------

@app.route("/submit", methods=["POST"])
def submit():
    kind = (request.form.get("kind") or "").strip().lower()
    if kind not in {"person", "photo", "story"}:
        return _thanks_html("Unrecognized submission type.", ok=False), 400

    submitter_name  = (request.form.get("submitter_name") or "").strip()
    submitter_email = (request.form.get("submitter_email") or "").strip()
    name_hint = (
        request.form.get("name") or
        request.form.get("title") or
        request.form.get("caption") or
        "submission"
    )
    sub_id = submission_id(kind, name_hint)

    data = {
        "id":          sub_id,
        "kind":        kind,
        "status":      "pending",
        "received_at": now_iso(),
        "submitter":   {"name": submitter_name, "email": submitter_email},
        "fields":      {k: v for k, v in request.form.items() if k not in {"kind", "submitter_name", "submitter_email"}},
    }

    # Photo upload
    if kind == "photo":
        upload = request.files.get("photo_file")
        fname = write_upload(upload, sub_id)
        data["upload"] = fname

    save_submission(data)
    safe_name = html.escape(submitter_name)
    safe_id = html.escape(sub_id)
    return _thanks_html(
        f"Thank you{', ' + safe_name if safe_name else ''}. "
        f"Your contribution has been received and is in the moderation queue. "
        f"Tracking ID: <code>{safe_id}</code>"
    ), 200


def _thanks_html(message, ok=True):
    color = "var(--forest)" if ok else "var(--flag-red)"
    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8"><title>Thank you — Quesenberry &amp; Harvey Family</title>
<link rel="stylesheet" href="/css/style.css">
</head><body>
<header class="site-header"><div class="shell"><p class="site-title"><a href="/">The Quesenberry &amp; Harvey Family</a></p></div></header>
<section class="branch-hero">
  <div class="shell">
    <p class="section-eyebrow">Submission Received</p>
    <h1>Thank you</h1>
    <p class="lede" style="color:{color};">{message}</p>
    <p style="margin-top:1.6rem;"><a class="cta-btn" href="/submit.html">Submit another</a> &nbsp; <a class="cta-btn" href="/" style="background:var(--ink-soft);border-color:var(--ink-soft);">Back to home</a></p>
  </div>
</section>
</body></html>"""


# ---- /admin (moderation queue) ---------------------------------------------

ADMIN_TPL = """<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8"><title>Admin — Submissions Queue</title>
<link rel="stylesheet" href="/css/style.css">
<style>
  .admin-list { display: grid; gap: 1.4rem; }
  .admin-card { background: var(--paper-2); border: 1px solid var(--rule); padding: 1.4rem 1.6rem; }
  .admin-card.status-approved { border-left: 4px solid var(--forest); }
  .admin-card.status-rejected { border-left: 4px solid var(--flag-red); opacity: 0.7; }
  .admin-card.status-pending  { border-left: 4px solid var(--rust); }
  .admin-card pre { background: #fbf6e7; padding: 0.6em 0.9em; font-family: var(--voice-archive); font-size: 0.84rem; overflow-x: auto; max-height: 320px; }
  .admin-card .actions { display: flex; gap: 0.6em; margin-top: 1em; }
  .admin-card .actions button { padding: 0.55em 1.1em; font-family: var(--voice-caps); letter-spacing: 0.16em; font-size: 0.78rem; text-transform: uppercase; cursor: pointer; border: 1px solid var(--rust); background: var(--paper); color: var(--rust); }
  .admin-card .actions button:hover { background: var(--rust); color: var(--paper); }
  .admin-card .actions button.danger { border-color: var(--flag-red); color: var(--flag-red); }
  .admin-card .actions button.danger:hover { background: var(--flag-red); color: var(--paper); }
  .admin-tabs { display: flex; gap: 0.4rem; margin: 1.6rem 0 1.4rem; }
  .admin-tabs a { font-family: var(--voice-caps); letter-spacing: 0.18em; font-size: 0.78rem; text-transform: uppercase; padding: 0.55em 1.1em; border: 1px solid var(--rule); background: var(--paper); color: var(--ink-soft); text-decoration: none; }
  .admin-tabs a.active { background: var(--rust); color: var(--paper); border-color: var(--rust); }
  .admin-card img { max-width: 320px; max-height: 240px; border: 1px solid var(--rule); margin-top: 0.6em; }
</style>
</head><body>
<header class="site-header"><div class="shell">
  <p class="site-title"><a href="/">The Quesenberry &amp; Harvey Family</a></p>
  <nav class="site-nav"><a href="/admin?status=pending">Pending</a><a href="/admin?status=approved">Approved</a><a href="/admin?status=rejected">Rejected</a><a href="/">Back to site</a></nav>
</div></header>

<section class="branch-hero">
  <div class="shell">
    <p class="section-eyebrow">Moderation Queue</p>
    <h1>{{ title }}</h1>
    <p class="lede">{{ count }} item{{ 's' if count != 1 else '' }} in this view.</p>
  </div>
</section>

<section><div class="shell">
  <div class="admin-tabs">
    <a href="/admin?status=pending"  {% if status == 'pending'  %}class="active"{% endif %}>Pending</a>
    <a href="/admin?status=approved" {% if status == 'approved' %}class="active"{% endif %}>Approved</a>
    <a href="/admin?status=rejected" {% if status == 'rejected' %}class="active"{% endif %}>Rejected</a>
  </div>

  {% if not items %}
    <p class="muted">No submissions in this view.</p>
  {% endif %}

  <div class="admin-list">
  {% for s in items %}
    <article class="admin-card status-{{ s.status }}">
      <p class="dates">{{ s.received_at }} · <strong>{{ s.kind|upper }}</strong> · {{ s.id }}</p>
      <p><strong>From:</strong> {{ s.submitter.name or '(anonymous)' }}{% if s.submitter.email %} &lt;{{ s.submitter.email }}&gt;{% endif %}</p>
      {% if s.upload %}
        <p><strong>Uploaded image:</strong> <a href="/uploads/{{ s.upload }}" target="_blank">{{ s.upload }}</a></p>
        <a href="/uploads/{{ s.upload }}" target="_blank"><img src="/uploads/{{ s.upload }}" alt="upload preview"></a>
      {% endif %}
      <p><strong>Fields:</strong></p>
      <pre>{{ s.fields | tojson(indent=2) }}</pre>

      <div class="actions">
        <form method="post" action="/admin/{{ s.id }}/approve" style="display:inline;">
          <button type="submit">✓ Mark approved</button>
        </form>
        <form method="post" action="/admin/{{ s.id }}/reject" style="display:inline;">
          <button type="submit">✗ Reject</button>
        </form>
        <form method="post" action="/admin/{{ s.id }}/delete" style="display:inline;" onsubmit="return confirm('Permanently delete?');">
          <button type="submit" class="danger">🗑 Delete</button>
        </form>
      </div>
    </article>
  {% endfor %}
  </div>

  <hr class="flourish">
  <p class="muted">To incorporate an approved submission into the site, copy the relevant fields into <code>data/people.json</code>, <code>data/photos.json</code>, <code>data/stories.json</code>, or <code>data/heirlooms.json</code>, run <code>python3 build.py</code>, commit and push.</p>
</div></section>
</body></html>"""


_ADMIN_ENV = Environment(autoescape=select_autoescape(default=True, default_for_string=True))
_ADMIN_TEMPLATE = _ADMIN_ENV.from_string(ADMIN_TPL)


@app.route("/admin")
@basic_auth_required
def admin():
    status = request.args.get("status", "pending")
    if status not in {"pending", "approved", "rejected"}:
        status = "pending"
    items = all_submissions(status=status)
    title = {"pending": "Pending Submissions",
             "approved": "Approved Submissions",
             "rejected": "Rejected Submissions"}[status]
    return _ADMIN_TEMPLATE.render(items=items, status=status, title=title, count=len(items))


@app.route("/admin/<sub_id>/<action>", methods=["POST"])
@basic_auth_required
def admin_action(sub_id, action):
    if action not in {"approve", "reject", "delete"}:
        return abort(400)
    s = load_submission(sub_id)
    if not s:
        return abort(404)
    if action == "delete":
        (SUBMISSIONS_DIR / f"{sub_id}.json").unlink(missing_ok=True)
        if s.get("upload"):
            (UPLOADS_DIR / s["upload"]).unlink(missing_ok=True)
    else:
        s["status"] = "approved" if action == "approve" else "rejected"
        s["moderated_at"] = now_iso()
        save_submission(s)
    return redirect(url_for("admin", status=request.args.get("from_status", "pending")))


# ---- health check ----------------------------------------------------------

@app.route("/healthz")
def health():
    return {"status": "ok", "submissions_dir": str(SUBMISSIONS_DIR), "exists": SUBMISSIONS_DIR.exists()}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port, debug=False)

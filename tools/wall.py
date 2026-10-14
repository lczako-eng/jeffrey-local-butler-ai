#!/usr/bin/env python3
"""
wall.py — the screen. One page, many screens.
=============================================

"Show me on the TV" and "show me on my phone" are the same build, so this is
one page your own machine serves. A phone opens it. A TV's browser opens it.
An old tablet propped on the kitchen counter opens it in kiosk mode and *is*
the clock. Nothing is cast, nothing is uploaded, nothing leaves the house.

It is built for the person it is actually for. Someone with memory loss does
not type a search query — they look at a wall while someone who loves them
says "look, that's Cuba, that's you." So: big pictures, big type, the date
and the place under each one, and a single box to type into.

    python tools/wall.py               # just this machine
    python tools/wall.py --lan         # the phone and the TV too

It opens on a quiet, empty screen. "On this day" is one button away, never
automatic: a living-room screen must not surprise anyone with a photograph.

SAFETY, because this is a family's whole life on a screen:
  * it listens on 127.0.0.1 ONLY unless you say --lan;
  * it always needs the link printed in your terminal: the passcode in that
    link is swapped for a private cookie on first open and taken out of the
    address bar, so it is not left in a TV's history;
  * pictures are never kept in the browser's cache;
  * it never shows a photograph from a moment the owner said he'd rather not
    talk about, anything on his 'never on the wall' list, or a photo that has
    been deleted; and 'on this day' never surfaces what his own rules say not
    to raise unprompted;
  * a big Hide button (and Escape) clears the screen instantly, and it hides
    itself after a while with nobody touching it. A wall in a living room
    has guests in front of it, and a photograph is a disclosure like any
    other;
  * there is no microphone unless this browser can understand speech on the
    device itself — a browser's usual speech service sends the voice to its
    maker, and this page promises nothing leaves.
"""

from __future__ import annotations

import argparse
import datetime as dt
import http.cookies
import io
import json
import os
import re
import secrets
import socket
import sys
import threading
import time
import traceback
import urllib.parse as up
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "connector"))
import home  # noqa: E402

THUMB = 480          # long edge, in pixels — enough for a 4K TV at grid size
STATE: dict = {}     # index, embedder (loaded lazily), passcode, cookie
_LOCK = threading.RLock()
_EMB_LOCK = threading.Lock()     # the model loads slowly; pictures must not wait
_HIDDEN_LOCK = threading.Lock()  # one thread works out what to hide; others reuse it
_MISSES: dict = {}   # client ip -> consecutive wrong passcodes
_MISS_LOCK = threading.Lock()
LOCKOUT_AFTER = 5    # wrong guesses before that address is refused outright
COOKIE = "jefferey_wall"
HIDDEN_TTL = 15      # seconds the owner's 'hide' decisions are cached

UNREACHABLE = ("The pictures can't be reached right now. Is the Self-Cloud "
               "drive plugged in and the computer awake?")
SOMETHING_WRONG = ("Something went wrong reading the pictures. The details are "
                   "in the window on the computer that runs this screen.")


# ------------------------------------------------------------------- data
def _index():
    """The photo index, opened once. Each thread gets its own SQLite
    connection from it (photo_index.PhotoIndex.db), so many pictures can
    load at once. Opening never creates an index: none means NoIndex."""
    from photo_index import PhotoIndex
    with _LOCK:
        if "index" not in STATE:
            STATE["index"] = PhotoIndex(STATE["index_path"], create=False)
        return STATE["index"]


def _embedder():
    """Loaded on the FIRST question that needs meaning, never at startup —
    so the wall comes up instantly and a pure 'Cuba, 2016' question never
    pays for a model it doesn't use."""
    with _EMB_LOCK:
        if "embedder" in STATE:
            return STATE["embedder"]
        from photo_index import Embedder
        man = _index().manifest()
        if not man:
            STATE["embedder"] = None
            return None
        try:
            STATE["embedder"] = Embedder(_index(), man["model"], man["pretrained"],
                                         offline=True)
        except Exception:
            STATE["embedder"] = None
        return STATE["embedder"]


def _conscience_data() -> dict | None:
    """The owner's conscience, read and never written. The wall only needs
    his decisions: what he declined, what he keeps off the wall, his rules."""
    p = Path(STATE.get("conscience_path") or home.conscience_path()).expanduser()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        if not STATE.get("warned_conscience"):
            STATE["warned_conscience"] = True
            print(f"  ! Could not read {p}. The wall still hides what the photo "
                  f"index knows was declined.", file=sys.stderr)
        return None


def _hidden():
    """(what to hide, a Reminisce for photo tags) — re-read when the
    conscience changes, and at least every HIDDEN_TTL seconds."""
    p = Path(STATE.get("conscience_path") or home.conscience_path()).expanduser()
    try:
        stamp = p.stat().st_mtime_ns
    except OSError:
        stamp = None
    with _HIDDEN_LOCK:
        cached = STATE.get("hidden")
        if cached and cached[0] == stamp and time.time() - cached[1] < HIDDEN_TTL:
            return cached[2]
        from reminisce import wall_rules
        value = wall_rules(STATE["index_path"], _conscience_data())
        STATE["hidden"] = (stamp, time.time(), value)
        return value


def _photo_tags(rem, place, country, taken_at) -> set[str]:
    if taken_at:
        try:
            tags, _why = rem.tags_for(country, [place] if place else [], taken_at[:10])
            return tags
        except ValueError:                   # an unreadable date: place words only
            pass
    return {str(t).lower() for t in (place, country) if t}


def allowed(sha: str, place, country, taken_at, automatic: bool) -> bool:
    """May this photograph appear on the wall? Never a declined moment's
    photo, never anything on the owner's 'never on the wall' list — and,
    for 'on this day' (shown without anyone asking), never a subject his
    rules say not to raise unprompted."""
    hidden, rem = _hidden()
    if sha in hidden["shas"]:
        return False
    tags = _photo_tags(rem, place, country, taken_at)
    if tags & hidden["off_wall"]:
        return False
    if automatic and tags & (hidden["unprompted"] | hidden["never_ask"]):
        return False
    return True


def known_places() -> set[str]:
    idx = _index()
    out = set()
    for col in ("place", "country"):
        out |= {r[0] for r in idx.db.execute(
            f"SELECT DISTINCT {col} FROM photos WHERE {col} IS NOT NULL "
            f"AND missing_since IS NULL")}
    return out


def search(question: str, top: int = 120) -> dict:
    import recall
    q = recall.parse(question, known_places())
    emb = _embedder() if q.semantic else None
    hits = []
    # Ask for more than will show: some are hidden or out of reach.
    for h in recall.run(_index(), q, emb, top=top * 3):
        if not allowed(h["sha256"], h["place"], h["country"], h["taken_at"], False):
            continue
        if not (h.get("path") and Path(h["path"]).is_file()):
            continue                     # deleted, or on a drive not plugged in
        hits.append({k: v for k, v in h.items() if k != "path"})
        if len(hits) >= top:
            break
    return {"asked": question, "reading": q.describe(),
            "note": q.notes[0] if q.notes else "", "hits": hits}


def on_this_day(top: int = 120) -> dict:
    """The question nobody thinks to ask — asked only when someone presses
    the button."""
    today = dt.date.today()
    idx = _index()
    rows = list(idx.db.execute(
        "SELECT sha256, path, rel, taken_at, place, country FROM photos "
        "WHERE taken_at IS NOT NULL AND substr(taken_at,6,5) = ? "
        "AND missing_since IS NULL ORDER BY taken_at DESC",
        (today.strftime("%m-%d"),)))
    hits = []
    for sha, path, rel, taken, place, country in rows:
        if not allowed(sha, place, country, taken, True):
            continue
        if idx.locate(path, rel) is None:
            continue
        # No `path`: the page only needs the id, the date and the place, and
        # an absolute filename ("2016_divorce_papers.jpg") is itself a
        # disclosure.
        hits.append({"sha256": sha, "taken_at": taken, "place": place,
                     "country": country, "score": None})
        if len(hits) >= top:
            break
    return {"asked": "on this day", "note": "" if hits else
            "No photographs from this day in other years.",
            "reading": f"photographs taken on {today.strftime('%B %-d')}, "
                       f"in other years", "hits": hits}


def thumbnail(sha: str) -> bytes | None:
    """Made once, kept beside the index. Never touches the original. Checked
    against the index every time, cached copy or not: a photo that was
    deleted, forgotten or hidden is not shown, and its copy is removed."""
    from PIL import Image
    if not re.fullmatch(r"[0-9a-f]{64}", sha or ""):
        return None
    idx = _index()
    row = idx.db.execute(
        "SELECT path, rel, missing_since, taken_at, place, country FROM photos "
        "WHERE sha256=?", (sha,)).fetchone()
    if not row or row[2] is not None:
        idx.drop_thumb(sha)                  # deleted or forgotten: its copy goes too
        return None
    path, rel, _miss, taken, place, country = row
    if not allowed(sha, place, country, taken, False):
        return None
    src = idx.locate(path, rel)
    if src is None:
        return None                          # not reachable now (drive unplugged)
    out = idx.thumb_path(sha)
    if out.exists():
        return out.read_bytes()
    try:
        from photo_index import open_image
        im = open_image(src)
        im.thumbnail((THUMB, THUMB))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=82)
        out.parent.mkdir(parents=True, exist_ok=True)
        # Written whole, then renamed into place: another request for the
        # same picture must never read a half-written copy.
        tmp = out.with_name(f".{out.name}.{threading.get_ident()}.tmp")
        tmp.write_bytes(buf.getvalue())
        os.replace(tmp, out)
        return buf.getvalue()
    except Exception:
        return None


# ------------------------------------------------------------------- page
PAGE = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Your life</title>
<style>
:root{--bg:#0b0b0d;--fg:#f2f2f4;--dim:#8b8b93;--line:#242428;--accent:#c9a227}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
 font:16px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
header{position:sticky;top:0;background:linear-gradient(var(--bg) 70%,transparent);
 padding:20px clamp(16px,4vw,48px) 16px;z-index:5}
.row{display:flex;gap:12px;align-items:center;max-width:1600px;margin:0 auto;flex-wrap:wrap}
input{flex:1;min-width:200px;background:#151518;border:1px solid var(--line);color:var(--fg);
 border-radius:14px;padding:16px 20px;font-size:clamp(17px,2.2vw,22px);outline:none}
input:focus{border-color:var(--accent)}
button{background:#151518;border:1px solid var(--line);color:var(--fg);
 border-radius:14px;padding:16px 20px;font-size:clamp(15px,2vw,19px);cursor:pointer}
button:hover{border-color:var(--accent)}
#hide{border-color:#5a4a12}
#reading{max-width:1600px;margin:10px auto 0;color:var(--dim);
 font-size:clamp(14px,1.6vw,17px);min-height:1.5em}
main{padding:8px clamp(16px,4vw,48px) 64px}
#grid{display:grid;gap:14px;max-width:1600px;margin:0 auto;
 grid-template-columns:repeat(auto-fill,minmax(min(280px,100%),1fr))}
figure{margin:0;background:#141417;border-radius:14px;overflow:hidden;
 border:1px solid var(--line)}
figure img{width:100%;aspect-ratio:1;object-fit:cover;display:block;background:#1c1c20}
.gone{aspect-ratio:1;display:flex;align-items:center;justify-content:center;
 color:var(--dim);padding:20px;text-align:center}
figcaption{padding:10px 12px;font-size:clamp(13px,1.4vw,16px);color:var(--dim)}
figcaption b{color:var(--fg);font-weight:600;display:block}
#empty{color:var(--dim);text-align:center;padding:80px 20px;
 font-size:clamp(16px,2vw,20px);max-width:640px;margin:0 auto}
#hidden{position:fixed;inset:0;background:var(--bg);display:none;z-index:99;
 align-items:center;justify-content:center;color:var(--dim);font-size:22px;
 text-align:center;padding:24px;cursor:pointer}
.priv{color:var(--dim);font-size:13px;text-align:center;padding:0 20px 40px}
</style></head><body>
<header>
 <div class="row">
  <input id="q" placeholder="type a place, a year, or what it looked like"
         autocomplete="off">
  <button id="mic" title="speak" style="display:none">&#127908;</button>
  <button id="today">On this day</button>
  <button id="hide">Hide</button>
 </div>
 <div id="reading"></div>
</header>
<main><div id="grid"></div><div id="empty">Type a place, a year, or what you'd
 like to see — for example “Cuba 2016” — and press return. Or press “On this
 day”.</div></main>
<div class="priv">These pictures come from this home's own computer, and this
 page sends nothing to the internet. The microphone button appears only when
 this browser can understand speech on this device itself. Press Hide (or
 Escape) to clear the screen.</div>
<div id="hidden">Hidden. Tap anywhere to show the pictures again.</div>
<script>
const grid = document.getElementById('grid'), reading = document.getElementById('reading'),
      empty = document.getElementById('empty'), q = document.getElementById('q'),
      veil = document.getElementById('hidden');
const UNREACHABLE = "The pictures can't be reached right now. Is the Self-Cloud drive plugged in and the computer awake?";
const NEEDS_LINK = "This screen needs the link shown on the computer that runs it. Please open that link again.";

function placeOf(h){
  if(h.place) return (h.country && h.country !== h.place) ? h.place+', '+h.country : h.place;
  return h.country || '';
}
function show(d){
  reading.textContent = (d && d.reading) || '';
  grid.replaceChildren();
  if(!d || d.error){
    empty.textContent = (d && d.error) || UNREACHABLE;
    return;
  }
  if(!d.hits || !d.hits.length){
    empty.textContent = d.note || 'Nothing matched that. Try a place, a year, or what it looked like.';
    return;
  }
  empty.textContent = '';
  for(const h of d.hits){
    const f = document.createElement('figure');
    const img = document.createElement('img');
    img.loading = 'lazy'; img.alt = '';
    img.src = '/thumb/' + encodeURIComponent(h.sha256);
    img.onerror = () => {
      const g = document.createElement('div');
      g.className = 'gone'; g.textContent = "This picture can't be shown right now.";
      img.replaceWith(g);
    };
    const cap = document.createElement('figcaption'), b = document.createElement('b');
    b.textContent = h.taken_at ? new Date(h.taken_at).toLocaleDateString(undefined,
                    {year:'numeric',month:'long',day:'numeric'}) : 'date unknown';
    cap.append(b, document.createTextNode(placeOf(h)));
    f.append(img, cap);
    grid.appendChild(f);
  }
}
async function getJSON(url){
  const ctl = new AbortController(), timer = setTimeout(() => ctl.abort(), 30000);
  try {
    const r = await fetch(url, {credentials: 'same-origin', cache: 'no-store', signal: ctl.signal});
    if(r.status === 403) return {error: NEEDS_LINK};
    let d = null;
    try { d = await r.json(); } catch(e) {}
    if(!r.ok || !d) return {error: (d && d.error) || UNREACHABLE};
    return d;
  } catch(e) {
    return {error: UNREACHABLE};
  } finally { clearTimeout(timer); }
}
async function ask(text){
  reading.textContent = 'looking…';
  show(await getJSON('/search?q=' + encodeURIComponent(text)));
}
async function today(){
  reading.textContent = 'looking…';
  show(await getJSON('/on-this-day'));
}
q.addEventListener('keydown', e => { if(e.key === 'Enter' && q.value.trim()) ask(q.value.trim()); });
document.getElementById('today').onclick = today;

// Hiding: a big button, Escape, a tap on the veil to come back — and it
// hides itself when nobody has touched it for a while.
const IDLE_MS = 10 * 60 * 1000;
let idle = null;
function hide(){ veil.style.display = 'flex'; }
function unhide(){ veil.style.display = 'none'; poke(); }
function poke(){ clearTimeout(idle); idle = setTimeout(hide, IDLE_MS); }
document.getElementById('hide').onclick = hide;
veil.addEventListener('click', unhide);
document.addEventListener('keydown', e => {
  if(e.key === 'Escape') { veil.style.display === 'flex' ? unhide() : hide(); }
});
for(const ev of ['pointerdown', 'keydown', 'touchstart', 'wheel']) document.addEventListener(ev, poke, {passive: true});
poke();

// Speech, ONLY if this browser promises to understand it on this device.
// A browser's usual speech service sends the voice to its maker; that would
// break the promise at the bottom of this page, so then there is no mic.
(async () => {
  const mic = document.getElementById('mic');
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if(!SR || !('processLocally' in SR.prototype) || typeof SR.available !== 'function') return;
  const lang = navigator.language || 'en-US';
  try {
    if(await SR.available({langs: [lang], processLocally: true}) !== 'available') return;
  } catch(e) { return; }
  const r = new SR();
  r.lang = lang; r.interimResults = false; r.processLocally = true;
  if(r.processLocally !== true) return;
  mic.style.display = '';
  mic.onclick = () => { mic.textContent = '…'; r.start(); };
  r.onresult = e => { const t = e.results[0][0].transcript; q.value = t; mic.textContent = '\\u{1F3A4}'; ask(t); };
  r.onerror = () => { mic.textContent = '\\u{1F3A4}'; };
})();
</script></body></html>"""


# ----------------------------------------------------------------- server
class Wall(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):            # the terminal stays readable
        pass

    def _send(self, code: int, body: bytes, ctype: str, extra: dict | None = None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        # Nothing here is kept by the browser: a TV or a guest's tablet
        # must not hold the family's photographs after the screen is closed.
        self.send_header("Cache-Control", "private, no-store")
        # This page never loads anything from anywhere else. Say so to the browser.
        self.send_header("Content-Security-Policy",
                         "default-src 'self'; img-src 'self' data:; "
                         "style-src 'unsafe-inline'; script-src 'unsafe-inline'; "
                         "frame-ancestors 'none'")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Content-Type-Options", "nosniff")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code: int = 200):
        self._send(code, json.dumps(obj).encode(), "application/json")

    def _host_ok(self) -> bool:
        """On this machine only, the request must name this machine. A web
        page elsewhere that points its own name at 127.0.0.1 gets nothing."""
        if STATE.get("lan"):
            return True
        host = (self.headers.get("Host") or "").strip().lower()
        port = STATE.get("port")
        return host in {f"127.0.0.1:{port}", f"localhost:{port}", f"[::1]:{port}"}

    def _cookie_ok(self) -> bool:
        raw = self.headers.get("Cookie")
        if not raw or not STATE.get("cookie"):
            return False
        try:
            jar = http.cookies.SimpleCookie(raw)
        except http.cookies.CookieError:
            return False
        got = jar.get(COOKIE)
        return bool(got) and secrets.compare_digest(
            got.value.encode(), STATE["cookie"].encode())

    def _code_ok(self, params) -> bool | None:
        """The passcode from the link, with a lockout. None = no code given.

        A 24-bit code and no lockout was measured at ~1,400 verified guesses a
        second from one process — the family's whole library in about an hour
        and a half from the wifi. Two changes: the code is now 128 bits, and an
        address that gets it wrong five times in a row is refused outright.
        """
        if "k" not in params:
            return None
        code = STATE.get("passcode") or ""
        who = self.client_address[0]
        with _MISS_LOCK:
            if _MISSES.get(who, 0) >= LOCKOUT_AFTER:
                return False               # no oracle, however long they try
        given = (params.get("k") or [""])[0]
        good = bool(code) and secrets.compare_digest(given.encode(), code.encode())
        with _MISS_LOCK:
            if good:
                _MISSES.pop(who, None)
            else:
                _MISSES[who] = _MISSES.get(who, 0) + 1
                if _MISSES[who] == LOCKOUT_AFTER:
                    print(f"  ! {who} got the passcode wrong {LOCKOUT_AFTER} "
                          f"times — refusing that address until restart.",
                          file=sys.stderr)
        return good

    def do_GET(self):
        u = up.urlparse(self.path)
        params = up.parse_qs(u.query)
        if not self._host_ok():
            self._send(403, b"This screen only answers on this computer.", "text/plain")
            return
        by_code = self._code_ok(params)
        if not (by_code or self._cookie_ok()):
            self._send(403, b"This screen needs the link shown on the computer "
                            b"that runs it. Please open that link again.",
                       "text/plain; charset=utf-8")
            return
        cookie = ({"Set-Cookie": f"{COOKIE}={STATE['cookie']}; HttpOnly; "
                                 f"SameSite=Strict; Path=/"} if by_code else {})
        try:
            if u.path == "/" and by_code:
                # Swap the passcode for the private cookie and take it out of
                # the address bar, so it is not left in a TV's history.
                self._send(303, b"", "text/plain", {**cookie, "Location": "/"})
            elif u.path == "/":
                self._send(200, PAGE.encode(), "text/html; charset=utf-8", cookie)
            elif u.path == "/search":
                term = (params.get("q") or [""])[0].strip()
                self._json(search(term) if term else
                           {"hits": [], "note": "Type a place, a year, or what it looked like."})
            elif u.path == "/on-this-day":
                self._json(on_this_day())
            elif u.path.startswith("/thumb/"):
                data = thumbnail(up.unquote(u.path.rsplit("/", 1)[-1]))
                if data:
                    self._send(200, data, "image/jpeg", cookie)
                else:
                    self._send(404, b"", "image/jpeg")
            elif u.path == "/status":
                idx = _index()
                n, = next(idx.db.execute(
                    "SELECT COUNT(*) FROM photos WHERE missing_since IS NULL"))
                self._json({"photos": n, "model_loaded": bool(STATE.get("embedder"))})
            else:
                self._send(404, b"no", "text/plain")
        except BrokenPipeError:
            pass
        except FileNotFoundError:          # no index here (the drive is unplugged?)
            self._json({"error": UNREACHABLE}, 503)
        except Exception:                  # a plain sentence on screen; details here
            traceback.print_exc()
            self._json({"error": SOMETHING_WRONG}, 500)


def lan_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))   # no packet is sent; just picks a route
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def serve(index_path: str, port: int, lan: bool = False,
          conscience_path: str | None = None) -> ThreadingHTTPServer:
    with _LOCK:
        for k in ("index", "embedder", "hidden", "warned_conscience"):
            STATE.pop(k, None)
        STATE["index_path"] = index_path
        STATE["conscience_path"] = conscience_path
        STATE["lan"] = bool(lan)
        # 128 bits, always — on this machine too, where any other program
        # could otherwise read the pictures. Nobody types it: it is in the
        # link you open, and the page swaps it for a private cookie.
        STATE["passcode"] = secrets.token_urlsafe(16)
        STATE["cookie"] = secrets.token_urlsafe(32)
    host = "0.0.0.0" if lan else "127.0.0.1"
    srv = ThreadingHTTPServer((host, port), Wall)
    srv.daemon_threads = True
    STATE["port"] = srv.server_address[1]
    return srv


def link(host: str = "127.0.0.1") -> str:
    return f"http://{host}:{STATE['port']}/?k={STATE['passcode']}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--index", default=str(home.index_path()))
    ap.add_argument("--port", type=int, default=8378)
    ap.add_argument("--lan", action="store_true",
                    help="let the phone and the TV reach it (asks for a passcode)")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()

    from photo_index import NoIndex, PhotoIndex
    try:
        PhotoIndex(a.index, create=False)      # say so plainly; never make one
    except NoIndex as e:
        print(f"\n  {e}\n")
        return 1
    srv = serve(a.index, a.port, a.lan)
    idx = _index()
    n, = next(idx.db.execute("SELECT COUNT(*) FROM photos WHERE missing_since IS NULL"))
    dated, = next(idx.db.execute(
        "SELECT COUNT(*) FROM photos WHERE taken_at IS NOT NULL AND missing_since IS NULL"))
    placed, = next(idx.db.execute(
        "SELECT COUNT(*) FROM photos WHERE place IS NOT NULL AND missing_since IS NULL"))

    print(f"\n  The wall is up.  {n} photographs — {dated} with a date, "
          f"{placed} with a place.\n")
    print(f"  On this machine   {link()}")
    if a.lan:
        print(f"  Phone / TV / pad  {link(lan_ip())}")
        print(f"\n  Being on the wifi is not the same as being allowed: each screen "
              f"needs this link.\n  It changes every time you start this.")
    else:
        print(f"\n  This machine only. Add --lan to reach it from the phone or TV.")
    print(f"\n  Nothing leaves this machine. Ctrl-C stops it.\n")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n  Wall down. Nothing is still running.\n")
    return 0


# ---------------------------------------------------------------- selftest
def selftest() -> int:
    """Starts a real server and talks to it over a real socket — the way
    `python tools/wall.py` does (index opened on the main thread first), and
    the way a browser does (many pictures at once)."""
    import http.client
    import http.cookiejar
    import shutil
    import tempfile
    import urllib.request
    from concurrent.futures import ThreadPoolExecutor
    from PIL import Image
    from photo_index import cmd_build, DEFAULT_MODEL

    td = Path(tempfile.mkdtemp(prefix="wall-selftest-"))
    try:
        pix = td / "pix"
        pix.mkdir()
        try:
            import piexif
            def stamp(name, when, lat, lon, colour):
                p = pix / name
                Image.new("RGB", (80, 80), colour).save(p, "JPEG")
                def dms(v):
                    v = abs(v); d = int(v); m = int((v - d) * 60)
                    return ((d, 1), (m, 1), (round((v-d-m/60)*360000), 100))
                piexif.insert(piexif.dump({
                    "Exif": {piexif.ExifIFD.DateTimeOriginal: when.encode()},
                    "GPS": {piexif.GPSIFD.GPSLatitudeRef: b"N",
                            piexif.GPSIFD.GPSLatitude: dms(lat),
                            piexif.GPSIFD.GPSLongitudeRef: b"W",
                            piexif.GPSIFD.GPSLongitude: dms(abs(lon))}}), str(p))
            for i, colour in enumerate(("teal", "navy", "maroon", "olive", "purple", "gray")):
                stamp(f"cuba{i}.jpg", f"2016:07:1{i} 12:00:00", 23.1394, -81.2714, colour)
        except ImportError:
            Image.new("RGB", (80, 80), "teal").save(pix / "plain.jpg")

        args = argparse.Namespace(index=str(td / "idx"), source=str(pix),
                                  model=DEFAULT_MODEL, pretrained="none",
                                  batch=4, limit=0, offline=True)
        cmd_build(args)

        srv = serve(str(td / "idx"), 0, lan=True,           # port 0 = pick a free one
                    conscience_path=str(td / "conscience.json"))
        _index()                 # as main() does: the index opened on THIS thread
        port = STATE["port"]
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{port}"
        code = STATE["passcode"]
        opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

        def get(path, use=None):
            fetch = use.open if use else urllib.request.urlopen
            with fetch(base + path, timeout=10) as r:
                return r.status, r.read(), r.headers

        # the passcode is not decoration
        for bad in ("/status", "/status?k=" + "0" * len(code)):
            try:
                get(bad)
                raise AssertionError("served the library without the passcode!")
            except urllib.error.HTTPError as e:
                assert e.code == 403, e.code

        # the link swaps the passcode for a private cookie and drops it from the URL
        st, body, hdr = get(f"/?k={code}", opener)
        assert st == 200 and b"<title>Your life</title>" in body
        assert b"http://" not in body.split(b"<script>")[0], \
            "the page reaches outside the house"
        assert b"today();\n</script>" not in body, "opens on 'on this day' by itself"
        st, body, _ = get("/status", opener)                 # cookie, no code
        assert st == 200 and json.loads(body)["photos"] >= 1
        assert "index" not in json.loads(body), "the index's location is shown"
        assert json.loads(body)["model_loaded"] is False, "loaded the model at startup"

        # a pure time+place question is answered WITHOUT loading the model
        st, body, _ = get("/search?q=" + up.quote("2016 in Cuba"), opener)
        d = json.loads(body)
        assert st == 200, st
        if d["hits"]:
            assert json.loads(get("/status", opener)[1])["model_loaded"] is False, \
                "loaded the model for a question that didn't need it"
            shas = [h["sha256"] for h in d["hits"]]
            st, img, hdr = get(f"/thumb/{shas[0]}", opener)
            assert st == 200 and img[:2] == b"\xff\xd8", "not a JPEG"
            assert "no-store" in hdr["Cache-Control"], hdr["Cache-Control"]
            assert (Path(td / "idx") / "thumbs" / f"{shas[0]}.jpg").exists(), "no cache"

            # many pictures at once, over kept-alive connections, like a browser
            cookie = f"{COOKIE}={STATE['cookie']}"

            def burst(_):
                c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
                codes = []
                for s in shas:
                    c.request("GET", f"/thumb/{s}", headers={"Cookie": cookie})
                    r = c.getresponse()
                    r.read()
                    codes.append(r.status)
                c.close()
                return codes
            with ThreadPoolExecutor(6) as pool:
                codes = [x for batch in pool.map(burst, range(6)) for x in batch]
            assert set(codes) == {200}, f"parallel thumbnails failed: {codes}"

        st, body, _ = get("/on-this-day", opener)
        assert st == 200 and "reading" in json.loads(body)

        try:
            get("/thumb/notarealsha", opener)
            raise AssertionError("a thumbnail that doesn't exist returned 200")
        except urllib.error.HTTPError as e:
            assert e.code == 404, (e.code, e.read()[:400])

        srv.shutdown()
        print("\n  ✓ the wall: passcode enforced and swapped for a private cookie,")
        print("    page opens quietly, a time+place question is answered without")
        print("    loading the model, thumbnails render, are never cached by the")
        print("    browser, and load many at once; nothing from outside the house.\n")
        return 0
    finally:
        shutil.rmtree(td, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())

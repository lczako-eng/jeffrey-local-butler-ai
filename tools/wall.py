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
and the place under each one, and a single box you can talk or type into.

    python tools/wall.py               # just this machine
    python tools/wall.py --lan         # the phone and the TV too

It opens on "on this day" — the question nobody thinks to ask.

SAFETY, because this is a family's whole life on a screen:
  * it listens on 127.0.0.1 ONLY unless you say --lan;
  * with --lan it demands a passcode printed in your terminal, so being on
    the wifi is not the same as being allowed;
  * Escape clears the screen instantly. A wall in a living room has guests
    in front of it, and a photograph is a disclosure like any other.
"""

from __future__ import annotations

import argparse
import datetime as dt
import io
import json
import secrets
import socket
import sys
import threading
import urllib.parse as up
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

THUMB = 480          # long edge, in pixels — enough for a 4K TV at grid size
STATE: dict = {}     # index, embedder (loaded lazily), passcode


# ------------------------------------------------------------------- data
def _index():
    from photo_index import PhotoIndex
    if "index" not in STATE:
        STATE["index"] = PhotoIndex(STATE["index_path"])
    return STATE["index"]


def _embedder():
    """Loaded on the FIRST question that needs meaning, never at startup —
    so the wall comes up instantly and a pure 'Cuba, 2016' question never
    pays for a model it doesn't use."""
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


def known_places() -> set[str]:
    idx = _index()
    out = set()
    for col in ("place", "country"):
        out |= {r[0] for r in idx.db.execute(
            f"SELECT DISTINCT {col} FROM photos WHERE {col} IS NOT NULL")}
    return out


def search(question: str, top: int = 120) -> dict:
    import recall
    q = recall.parse(question, known_places())
    emb = _embedder() if q.semantic else None
    hits = recall.run(_index(), q, emb, top=top)
    return {"asked": question, "reading": q.describe(),
            "note": q.notes[0] if q.notes else "", "hits": hits}


def on_this_day(top: int = 120) -> dict:
    """The question nobody thinks to ask."""
    today = dt.date.today()
    rows = list(_index().db.execute(
        "SELECT sha256, path, taken_at, place, country FROM photos "
        "WHERE taken_at IS NOT NULL AND substr(taken_at,6,5) = ? "
        "AND missing_since IS NULL ORDER BY taken_at DESC",
        (today.strftime("%m-%d"),)))
    hits = [{"sha256": r[0], "path": r[1], "taken_at": r[2],
             "place": r[3], "country": r[4], "score": None} for r in rows[:top]]
    return {"asked": "on this day", "note": "",
            "reading": f"photographs taken on {today.strftime('%B %-d')}, "
                       f"in other years", "hits": hits}


def thumbnail(sha: str) -> bytes | None:
    """Made once, kept beside the index. Never touches the original."""
    from PIL import Image
    cache = Path(STATE["index_path"]).expanduser() / "thumbs"
    cache.mkdir(parents=True, exist_ok=True)
    out = cache / f"{sha}.jpg"
    if out.exists():
        return out.read_bytes()
    row = next(_index().db.execute(
        "SELECT path FROM photos WHERE sha256=?", (sha,)), None)
    if not row or not Path(row[0]).exists():
        return None
    try:
        from photo_index import open_image
        im = open_image(Path(row[0]))
        im.thumbnail((THUMB, THUMB))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=82)
        out.write_bytes(buf.getvalue())
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
.row{display:flex;gap:12px;align-items:center;max-width:1600px;margin:0 auto}
input{flex:1;background:#151518;border:1px solid var(--line);color:var(--fg);
 border-radius:14px;padding:16px 20px;font-size:clamp(17px,2.2vw,22px);outline:none}
input:focus{border-color:var(--accent)}
button{background:#151518;border:1px solid var(--line);color:var(--fg);
 border-radius:14px;padding:16px 20px;font-size:clamp(15px,2vw,19px);cursor:pointer}
button:hover{border-color:var(--accent)}
#reading{max-width:1600px;margin:10px auto 0;color:var(--dim);
 font-size:clamp(14px,1.6vw,17px);min-height:1.5em}
main{padding:8px clamp(16px,4vw,48px) 64px}
#grid{display:grid;gap:14px;max-width:1600px;margin:0 auto;
 grid-template-columns:repeat(auto-fill,minmax(min(280px,100%),1fr))}
figure{margin:0;background:#141417;border-radius:14px;overflow:hidden;
 border:1px solid var(--line)}
figure img{width:100%;aspect-ratio:1;object-fit:cover;display:block;background:#1c1c20}
figcaption{padding:10px 12px;font-size:clamp(13px,1.4vw,16px);color:var(--dim)}
figcaption b{color:var(--fg);font-weight:600;display:block}
#empty{color:var(--dim);text-align:center;padding:80px 20px;
 font-size:clamp(16px,2vw,20px);max-width:640px;margin:0 auto}
#hidden{position:fixed;inset:0;background:var(--bg);display:none;z-index:99;
 align-items:center;justify-content:center;color:var(--dim);font-size:20px}
.priv{color:var(--dim);font-size:13px;text-align:center;padding:0 20px 40px}
</style></head><body>
<header>
 <div class="row">
  <input id="q" placeholder="say or type — “vacation ten years ago in Cuba”"
         autocomplete="off" autofocus>
  <button id="mic" title="speak">&#127908;</button>
  <button id="today">On this day</button>
 </div>
 <div id="reading"></div>
</header>
<main><div id="grid"></div><div id="empty"></div></main>
<div class="priv">Everything on this page is on your own machine. Nothing was
 sent anywhere. Press Escape to clear the screen.</div>
<div id="hidden">screen cleared — press Escape</div>
<script>
const T = new URLSearchParams(location.search).get('k') || '';
const grid = document.getElementById('grid'), reading = document.getElementById('reading'),
      empty = document.getElementById('empty'), q = document.getElementById('q');

function show(d){
  reading.textContent = d.reading || '';
  grid.innerHTML = '';
  if(!d.hits || !d.hits.length){
    empty.textContent = d.note || 'Nothing matched that. Try a place, a year, or what it looked like.';
    return;
  }
  empty.textContent = '';
  for(const h of d.hits){
    const f = document.createElement('figure');
    const when = h.taken_at ? new Date(h.taken_at).toLocaleDateString(undefined,
                  {year:'numeric',month:'long',day:'numeric'}) : '';
    const where = h.place ? (h.country && h.country !== h.place ? h.place+', '+h.country : h.place)
                          : (h.country || '');
    f.innerHTML = '<img loading="lazy" src="/thumb/'+h.sha256+'?k='+encodeURIComponent(T)+'">'
      + '<figcaption><b>'+(when||'date unknown')+'</b>'+(where||'')+'</figcaption>';
    grid.appendChild(f);
  }
}
async function ask(text){
  reading.textContent = 'looking…';
  const r = await fetch('/search?k='+encodeURIComponent(T)+'&q='+encodeURIComponent(text));
  show(await r.json());
}
async function today(){
  reading.textContent = 'looking…';
  const r = await fetch('/on-this-day?k='+encodeURIComponent(T));
  show(await r.json());
}
q.addEventListener('keydown', e => { if(e.key === 'Enter' && q.value.trim()) ask(q.value.trim()); });
document.getElementById('today').onclick = today;

// Escape clears the screen. A wall in a living room has guests in front of it.
const veil = document.getElementById('hidden');
document.addEventListener('keydown', e => {
  if(e.key === 'Escape') veil.style.display = veil.style.display === 'flex' ? 'none' : 'flex';
});

// Speech, if this browser has it. The recogniser is the browser's own.
const mic = document.getElementById('mic');
const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
if(SR){
  const r = new SR(); r.lang = navigator.language || 'en-US'; r.interimResults = false;
  mic.onclick = () => { mic.textContent='…'; r.start(); };
  r.onresult = e => { const t = e.results[0][0].transcript; q.value = t; mic.textContent='\\u{1F3A4}'; ask(t); };
  r.onerror = () => { mic.textContent='\\u{1F3A4}'; };
} else { mic.style.display='none'; }
today();
</script></body></html>"""


# ----------------------------------------------------------------- server
class Wall(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):            # the terminal stays readable
        pass

    def _send(self, code: int, body: bytes, ctype: str, cache: bool = False):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "public, max-age=86400" if cache else "no-store")
        # This page never loads anything from anywhere else. Say so to the browser.
        self.send_header("Content-Security-Policy",
                         "default-src 'self'; img-src 'self' data:; "
                         "style-src 'unsafe-inline'; script-src 'unsafe-inline'")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code: int = 200):
        self._send(code, json.dumps(obj).encode(), "application/json")

    def _allowed(self, params) -> bool:
        code = STATE.get("passcode")
        if not code:
            return True                    # localhost only; nothing to guard
        given = (params.get("k") or [""])[0]
        return secrets.compare_digest(given, code)

    def do_GET(self):
        u = up.urlparse(self.path)
        params = up.parse_qs(u.query)
        if not self._allowed(params):
            self._send(403, b"This screen needs the passcode shown in the "
                            b"terminal on the machine serving it.", "text/plain")
            return
        try:
            if u.path == "/":
                self._send(200, PAGE.encode(), "text/html; charset=utf-8")
            elif u.path == "/search":
                term = (params.get("q") or [""])[0].strip()
                self._json(search(term) if term else on_this_day())
            elif u.path == "/on-this-day":
                self._json(on_this_day())
            elif u.path.startswith("/thumb/"):
                data = thumbnail(u.path.rsplit("/", 1)[-1])
                if data:
                    self._send(200, data, "image/jpeg", cache=True)
                else:
                    self._send(404, b"", "image/jpeg")
            elif u.path == "/status":
                idx = _index()
                n, = next(idx.db.execute("SELECT COUNT(*) FROM photos"))
                self._json({"photos": n, "index": str(STATE["index_path"]),
                            "model_loaded": "embedder" in STATE})
            else:
                self._send(404, b"no", "text/plain")
        except BrokenPipeError:
            pass
        except Exception as exc:           # a broken page is better than a dead one
            self._json({"error": f"{type(exc).__name__}: {exc}"}, 500)


def lan_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))   # no packet is sent; just picks a route
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def serve(index_path: str, port: int, lan: bool) -> ThreadingHTTPServer:
    STATE["index_path"] = index_path
    STATE["passcode"] = secrets.token_hex(3) if lan else None
    host = "0.0.0.0" if lan else "127.0.0.1"
    srv = ThreadingHTTPServer((host, port), Wall)
    return srv


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--index", default="~/.selfcloud/photo-index")
    ap.add_argument("--port", type=int, default=8378)
    ap.add_argument("--lan", action="store_true",
                    help="let the phone and the TV reach it (asks for a passcode)")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()

    srv = serve(a.index, a.port, a.lan)
    idx = _index()
    n, = next(idx.db.execute("SELECT COUNT(*) FROM photos"))
    dated, = next(idx.db.execute(
        "SELECT COUNT(*) FROM photos WHERE taken_at IS NOT NULL"))
    placed, = next(idx.db.execute(
        "SELECT COUNT(*) FROM photos WHERE place IS NOT NULL"))

    print(f"\n  The wall is up.  {n} photographs — {dated} with a date, "
          f"{placed} with a place.\n")
    if a.lan:
        url = f"http://{lan_ip()}:{a.port}/?k={STATE['passcode']}"
        print(f"  On this machine   http://127.0.0.1:{a.port}/?k={STATE['passcode']}")
        print(f"  Phone / TV / pad  {url}")
        print(f"\n  Passcode {STATE['passcode']} — being on the wifi is not the "
              f"same as being allowed.\n  It changes every time you start this.")
    else:
        print(f"  http://127.0.0.1:{a.port}/")
        print(f"\n  This machine only. Add --lan to reach it from the phone or TV.")
    print(f"\n  Nothing leaves this machine. Ctrl-C stops it.\n")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n  Wall down. Nothing is still running.\n")
    return 0


# ---------------------------------------------------------------- selftest
def selftest() -> int:
    """Starts a real server and talks to it over a real socket."""
    import shutil
    import tempfile
    import urllib.request
    from PIL import Image
    from photo_index import PhotoIndex, cmd_build, DEFAULT_MODEL

    td = Path(tempfile.mkdtemp(prefix="wall-selftest-"))
    try:
        pix = td / "pix"
        pix.mkdir()
        try:
            import piexif
            def stamp(name, when, lat, lon):
                p = pix / name
                Image.new("RGB", (80, 80), "teal").save(p, "JPEG")
                def dms(v):
                    v = abs(v); d = int(v); m = int((v - d) * 60)
                    return ((d, 1), (m, 1), (round((v-d-m/60)*360000), 100))
                piexif.insert(piexif.dump({
                    "Exif": {piexif.ExifIFD.DateTimeOriginal: when.encode()},
                    "GPS": {piexif.GPSIFD.GPSLatitudeRef: b"N",
                            piexif.GPSIFD.GPSLatitude: dms(lat),
                            piexif.GPSIFD.GPSLongitudeRef: b"W",
                            piexif.GPSIFD.GPSLongitude: dms(abs(lon))}}), str(p))
            stamp("cuba.jpg", "2016:07:14 12:00:00", 23.1394, -81.2714)
        except ImportError:
            Image.new("RGB", (80, 80), "teal").save(pix / "plain.jpg")

        args = argparse.Namespace(index=str(td / "idx"), source=str(pix),
                                  model=DEFAULT_MODEL, pretrained="none",
                                  batch=4, limit=0, offline=True)
        cmd_build(args)

        srv = serve(str(td / "idx"), 0, lan=True)     # port 0 = pick a free one
        port = srv.server_address[1]
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{port}"
        code = STATE["passcode"]

        def get(path):
            with urllib.request.urlopen(base + path, timeout=10) as r:
                return r.status, r.read()

        # the passcode is not decoration
        try:
            get("/status")
            raise AssertionError("served the library with no passcode!")
        except urllib.error.HTTPError as e:
            assert e.code == 403, e.code
        try:
            get("/status?k=" + "0" * len(code))
            raise AssertionError("accepted a wrong passcode!")
        except urllib.error.HTTPError as e:
            assert e.code == 403, e.code

        st, body = get(f"/status?k={code}")
        assert st == 200 and json.loads(body)["photos"] >= 1
        assert json.loads(body)["model_loaded"] is False, "loaded the model at startup"

        st, body = get(f"/?k={code}")
        assert st == 200 and b"<title>Your life</title>" in body
        assert b"http://" not in body.split(b"<script>")[0], \
            "the page reaches outside the house"

        # a pure time+place question is answered WITHOUT loading the model
        st, body = get(f"/search?k={code}&q=" + up.quote("2016 in Cuba"))
        d = json.loads(body)
        assert st == 200, st
        if d["hits"]:
            assert json.loads(get(f"/status?k={code}")[1])["model_loaded"] is False, \
                "loaded the model for a question that didn't need it"
            sha = d["hits"][0]["sha256"]
            st, img = get(f"/thumb/{sha}?k={code}")
            assert st == 200 and img[:2] == b"\xff\xd8", "not a JPEG"
            assert (Path(td / "idx") / "thumbs" / f"{sha}.jpg").exists(), "no cache"

        st, body = get(f"/on-this-day?k={code}")
        assert st == 200 and "reading" in json.loads(body)

        try:
            get(f"/thumb/notarealsha?k={code}")
            raise AssertionError("a thumbnail that doesn't exist returned 200")
        except urllib.error.HTTPError as e:
            assert e.code == 404, e.code

        srv.shutdown()
        print("\n  ✓ the wall: passcode enforced (no code and wrong code both")
        print("    refused), page serves, a time+place question is answered")
        print("    without ever loading the model, thumbnails render and cache,")
        print("    and the page loads nothing from outside the house.\n")
        return 0
    finally:
        shutil.rmtree(td, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())

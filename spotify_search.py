# Diekstrak dari telegram-control-local-opensource.sh baris 8702-8768
# Fungsi shell asal: spotify_search()
# Dipanggil lewat: python - <<'PY' 2>>"${LOG_FILE:-/dev/null}"
import os, sys, json, time, base64, urllib.request, urllib.parse

E = os.environ
q = E["Q"]

def get(url, headers=None, data=None):
    req = urllib.request.Request(url, data=data, headers=headers or {})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)

def spotify():
    cid, sec = E.get("SID", ""), E.get("SSEC", "")
    if not cid or not sec:
        raise RuntimeError("kunci Spotify kosong")
    tok = None
    try:
        t = json.load(open(E["TOKF"]))
        if t["exp"] > time.time() + 30:
            tok = t["tok"]
    except Exception:
        pass
    if not tok:
        auth = base64.b64encode((cid + ":" + sec).encode()).decode()
        j = get("https://accounts.spotify.com/api/token",
                {"Authorization": "Basic " + auth, "Content-Type": "application/x-www-form-urlencoded"},
                b"grant_type=client_credentials")
        tok = j["access_token"]
        with open(E["TOKF"], "w") as f:
            json.dump({"tok": tok, "exp": time.time() + int(j.get("expires_in", 3600))}, f)
        os.chmod(E["TOKF"], 0o600)
    out = []
    for off in (0, 10):   # batas Spotify sejak Feb 2026: maksimal 10 hasil per permintaan
        try:
            j = get("https://api.spotify.com/v1/search?" + urllib.parse.urlencode(
                {"q": q, "type": "track", "limit": 10, "offset": off}), {"Authorization": "Bearer " + tok})
        except Exception:
            if off == 0:
                raise
            break
        for it in j["tracks"]["items"]:
            out.append({"title": it.get("name") or "?",
                        "artist": ", ".join(a.get("name", "") for a in it.get("artists", [])),
                        "ms": it.get("duration_ms") or 0})
    return out

def itunes():
    j = get("https://itunes.apple.com/search?" + urllib.parse.urlencode(
        {"term": q, "media": "music", "entity": "song", "limit": 20, "country": E.get("CC", "ID")}))
    return [{"title": it.get("trackName") or "?", "artist": it.get("artistName") or "",
             "ms": it.get("trackTimeMillis") or 0} for it in j.get("results", [])]

src = E.get("SRC", "auto")
items = []
if src in ("auto", "spotify"):
    try:
        items = spotify()
    except Exception as e:
        print("[spotify] gagal: %s" % e, file=sys.stderr)
if not items and src in ("auto", "itunes"):
    try:
        items = itunes()
    except Exception as e:
        print("[itunes] gagal: %s" % e, file=sys.stderr)
if not items:
    sys.exit(1)
with open(E["OUT"], "w", encoding="utf-8") as f:
    json.dump({"q": q, "items": items}, f, ensure_ascii=False)

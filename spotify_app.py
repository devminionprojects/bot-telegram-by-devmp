#!/usr/bin/env python3
# Diekstrak dari telegram-control-local-opensource.sh baris 8915-12422
# Fungsi shell asal: spotify_app_start()
# Dipanggil lewat: cat > "$SPOTIFY_APP_PY" <<'SPOTIFY_APP_EOF'
"""
Mini App pencari lagu bergaya Spotify untuk bot Telegram.

Satu file, tanpa pustaka tambahan (hanya Python standar). Isinya:
  - halaman HTML (tab Cari + Ruang Global) yang dibuka dari tombol di bot
  - API kecil: /api/search, /api/play, /api/recent
Alur putar: ketuk lagu -> server menaruh permintaan di ~/.spotify_queue -> bot (check_spotify_queue)
mengambilnya dan menjalankan fitur play yang sudah ada (video + mp3 dari YouTube).

Keamanan: setiap permintaan API wajib membawa initData Telegram yang valid (tanda tangan HMAC dengan token bot),
dan ID pengirimnya harus pemilik / terdaftar di ~/.telegram_extra_ids dan tidak sedang diblokir.
Jadi orang yang tahu alamat halamannya tetap tidak bisa memakai API tanpa membukanya lewat bot.

Jalankan lewat jalankan-spotify-app.sh (variabelnya diambil dari skrip bot).
"""
import os, sys, json, time, hmac, hashlib, base64, threading, subprocess, re, glob, shutil
import urllib.request, urllib.parse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

HOME = os.path.expanduser("~")
E = os.environ
TOKEN = E.get("TELEGRAM_TOKEN", "")
OWNER = E.get("OWNER_CHAT_ID", "")
TG_API = E.get("TELEGRAM_API", "https://api.telegram.org").rstrip("/")
EXTRA_IDS = E.get("EXTRA_IDS_FILE", HOME + "/.telegram_extra_ids")
BLOCKED = E.get("BLOCKED_FILE", HOME + "/.telegram_blocked")
QUEUE = E.get("SPOTIFY_QUEUE_FILE", HOME + "/.spotify_queue")
RECENT_FILE = HOME + "/.spotify_recent.json"
PORT = int(E.get("SPOTIFY_APP_PORT", "8090"))
HOST = E.get("SPOTIFY_APP_HOST", "127.0.0.1")
SRC = E.get("SPOTIFY_SOURCE") or "auto"          # auto | spotify | itunes
SID = E.get("SPOTIFY_CLIENT_ID", "")
SSEC = E.get("SPOTIFY_CLIENT_SECRET", "")
COUNTRY = E.get("SPOTIFY_COUNTRY") or "ID"

if not TOKEN or not OWNER:
    sys.exit("TELEGRAM_TOKEN dan OWNER_CHAT_ID wajib diisi (lihat jalankan-spotify-app.sh)")

LOCK = threading.Lock()
_cache = {}                 # q -> (waktu, hasil)
_tok = {"v": "", "exp": 0}  # token Spotify (disimpan di memori saja)
_last_play = {}             # uid -> waktu terakhir (batas laju)


# ---------------------------------------------------------------- validasi pengguna
def check_init(init):
    """Cek initData Telegram. Kembalikan dict user kalau sah, selain itu None."""
    try:
        p = dict(urllib.parse.parse_qsl(init, keep_blank_values=True))
        h = p.pop("hash", "")
        s = "\n".join("%s=%s" % (k, v) for k, v in sorted(p.items()))
        secret = hmac.new(b"WebAppData", TOKEN.encode(), hashlib.sha256).digest()
        calc = hmac.new(secret, s.encode(), hashlib.sha256).hexdigest()
        if not h or not hmac.compare_digest(calc, h):
            return None
        if time.time() - int(p.get("auth_date", "0")) > 86400:
            return None
        u = json.loads(p.get("user", "{}"))
        return u if u.get("id") else None
    except Exception:
        return None


def allowed(uid):
    uid = str(uid)
    if uid != OWNER:
        try:
            for line in open(BLOCKED, encoding="utf-8"):
                if line.split("\t", 1)[0].strip() == uid:
                    return False
        except OSError:
            pass
        try:
            return uid in {l.strip() for l in open(EXTRA_IDS, encoding="utf-8")}
        except OSError:
            return False
    return True


# ---------------------------------------------------------------- pencarian lagu
def http_json(url, headers=None, data=None):
    req = urllib.request.Request(url, data=data, headers=headers or {})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def spotify_token():
    if not SID or not SSEC:
        raise RuntimeError("kunci Spotify kosong")
    with LOCK:
        if _tok["v"] and _tok["exp"] > time.time() + 30:
            return _tok["v"]
    auth = base64.b64encode((SID + ":" + SSEC).encode()).decode()
    j = http_json("https://accounts.spotify.com/api/token",
                  {"Authorization": "Basic " + auth, "Content-Type": "application/x-www-form-urlencoded"},
                  b"grant_type=client_credentials")
    with LOCK:
        _tok["v"] = j["access_token"]
        _tok["exp"] = time.time() + int(j.get("expires_in", 3600))
        return _tok["v"]


def search_spotify(q):
    tok = spotify_token()
    out = []
    for off in (0, 10):   # sejak Feb 2026 Spotify membatasi maksimal 10 hasil per permintaan
        try:
            j = http_json("https://api.spotify.com/v1/search?" + urllib.parse.urlencode(
                {"q": q, "type": "track", "limit": 10, "offset": off}), {"Authorization": "Bearer " + tok})
        except Exception:
            if off == 0:
                raise
            break
        for it in j["tracks"]["items"]:
            imgs = (it.get("album") or {}).get("images") or []
            cover = (imgs[1] if len(imgs) > 1 else imgs[0])["url"] if imgs else ""
            out.append({"title": it.get("name") or "?",
                        "artist": ", ".join(a.get("name", "") for a in it.get("artists", [])),
                        "ms": it.get("duration_ms") or 0, "cover": cover, "preview": ""})
    return out


def search_itunes(q):
    j = http_json("https://itunes.apple.com/search?" + urllib.parse.urlencode(
        {"term": q, "media": "music", "entity": "song", "limit": 20, "country": COUNTRY}))
    out = []
    for it in j.get("results", []):
        cover = (it.get("artworkUrl100") or "").replace("100x100bb", "200x200bb")
        out.append({"title": it.get("trackName") or "?", "artist": it.get("artistName") or "",
                    "ms": it.get("trackTimeMillis") or 0, "cover": cover,
                    "preview": good_preview(it.get("previewUrl"))})
    return out


def good_preview(u):
    return u if isinstance(u, str) and u.startswith("https://") and len(u) < 500 else ""


_prev_cache = {}


def find_preview(title, artist):
    """Cuplikan 30 detik dari iTunes untuk lagu ini (dipakai pemutar di Mini App, tanpa YouTube)."""
    key = (clean(title, 120) + " " + clean(artist, 80).split(",")[0]).strip().lower()
    if not key:
        return ""
    with LOCK:
        if key in _prev_cache:
            return _prev_cache[key]
    url = ""
    try:
        j = http_json("https://itunes.apple.com/search?" + urllib.parse.urlencode(
            {"term": key, "media": "music", "entity": "song", "limit": 5, "country": COUNTRY}))
        for it in j.get("results", []):
            if good_preview(it.get("previewUrl")):
                url = it["previewUrl"]
                break
    except Exception as e:
        sys.stderr.write("[preview] gagal: %s\n" % e)
        return ""
    with LOCK:
        if len(_prev_cache) > 500:
            _prev_cache.clear()
        _prev_cache[key] = url
    return url


def search(q):
    key = q.lower()
    with LOCK:
        c = _cache.get(key)
        if c and time.time() - c[0] < 600:
            return c[1]
    items, err = [], None
    if SRC in ("auto", "spotify"):
        try:
            items = search_spotify(q)
        except Exception as e:
            err = e
    if not items and SRC in ("auto", "itunes"):
        try:
            items = search_itunes(q)
        except Exception as e:
            err = e
    if not items and err:
        raise err
    with LOCK:
        if len(_cache) > 200:
            _cache.clear()
        _cache[key] = (time.time(), items)
    return items


# ---------------------------------------------------------------- putar + ruang global
def clean(s, n):
    return " ".join(str(s).replace("|", " ").replace("\r", " ").replace("\n", " ").split())[:n]


def tg_notify(chat, text):
    try:
        data = urllib.parse.urlencode({"chat_id": chat, "text": text}).encode()
        urllib.request.urlopen(urllib.request.Request("%s/bot%s/sendMessage" % (TG_API, TOKEN), data=data),
                               timeout=10).read()
    except Exception:
        pass


def recent_load():
    try:
        return json.load(open(RECENT_FILE, encoding="utf-8"))
    except Exception:
        return []


def recent_uniq(rec):
    seen, out = set(), []
    for r in rec:
        if not isinstance(r, dict):
            continue
        k = (str(r.get("title", "")).lower(), str(r.get("artist", "")).lower(), str(r.get("who", "")).lower())
        if k in seen:
            continue
        seen.add(k)
        out.append(r)
    return out


def enqueue_play(user, title, artist, cover):
    title, artist = clean(title, 120), clean(artist, 80)
    if not title:
        raise ValueError("judul kosong")
    with LOCK:
        rec = recent_load()
        if not (isinstance(cover, str) and cover.startswith("https://") and len(cover) < 400):
            cover = ""
        who = clean(user.get("first_name") or user.get("username") or "Seseorang", 30)
        # satu lagu dari satu orang cuma tampil SEKALI (yang terbaru), supaya ganti-ganti lagu tidak menumpuk/nyepam
        rec = recent_uniq(rec)
        k = (title.lower(), artist.lower(), who.lower())
        rec = [r for r in rec if (str(r.get("title", "")).lower(), str(r.get("artist", "")).lower(), str(r.get("who", "")).lower()) != k]
        rec.insert(0, {"title": title, "artist": artist, "cover": cover, "who": who, "ts": int(time.time())})
        json.dump(rec[:30], open(RECENT_FILE, "w", encoding="utf-8"), ensure_ascii=False)


# ---------------------------------------------------------------- lagu penuh dari YouTube, diputar di Mini App
YT_COOKIES = E.get("YT_COOKIES", HOME + "/yt-cookies.txt")
CACHE = HOME + "/.spotify_cache"
YT_MAX = int(E.get("SPOTIFY_YT_MAX", "900") or 900)     # detik; video lebih panjang dari ini ditolak
CACHE_KEEP = int(E.get("SPOTIFY_CACHE_KEEP", "40") or 40)   # jumlah lagu terakhir yang disimpan di cache
try:
    os.makedirs(CACHE, exist_ok=True)
except OSError:
    pass

# ---- video klip untuk kartu "Sedang diputar" (video tanpa suara, diputar sinkron dengan audio)
VIDEO_ON = (E.get("SPOTIFY_VIDEO", "1") or "1") != "0"        # isi 0 untuk mematikan fitur video
VCACHE = HOME + "/.spotify_vcache"
VCACHE_KEEP = int(E.get("SPOTIFY_VIDEO_KEEP", "8") or 8)       # jumlah video terakhir yang disimpan (video jauh lebih besar dari audio)
VIDEO_H = int(E.get("SPOTIFY_VIDEO_H", "360") or 360)          # tinggi video maksimal (360 = hemat kuota dan penyimpanan)
VMIME = {".mp4": "video/mp4", ".webm": "video/webm", ".mkv": "video/x-matroska"}
_vsem = threading.Semaphore(1)     # unduh video satu per satu supaya HP server tidak berat
_vlocks = {}
_vfail = {}                        # id video -> waktu gagal terakhir (jangan dicoba terus-menerus)
_vbusy = set()                     # id video yang sedang diunduh
try:
    os.makedirs(VCACHE, exist_ok=True)
except OSError:
    pass


def vcached_file(vid):
    for f in glob.glob(os.path.join(VCACHE, vid + ".*")):
        if os.path.splitext(f)[1].lower() in VMIME and os.path.getsize(f) > 0:
            return f
    return ""


def vprune():
    files = [f for f in glob.glob(os.path.join(VCACHE, "*")) if os.path.isfile(f) and os.path.splitext(f)[1].lower() in VMIME]
    files.sort(key=lambda f: os.path.getmtime(f), reverse=True)
    for f in files[VCACHE_KEEP:]:
        try:
            os.remove(f)
        except OSError:
            pass


def video_fetch(vid):
    f = vcached_file(vid)
    if f:
        return f
    with LOCK:
        lk = _vlocks.setdefault(vid, threading.Lock())
    with lk:
        f = vcached_file(vid)
        if f:
            return f
        _vbusy.add(vid)
        try:
            with _vsem:
                h = VIDEO_H
                fmt = "bestvideo[height<=%d][vcodec^=avc1][ext=mp4]/bestvideo[height<=%d][ext=mp4]/bestvideo[height<=%d]" % (h, h, h)
                subprocess.run(["yt-dlp", "--no-playlist", "--no-warnings", *ck_args(), "--max-filesize", "90M",
                                "-f", fmt, "-o", os.path.join(VCACHE, "%(id)s.%(ext)s"),
                                "https://www.youtube.com/watch?v=" + vid], capture_output=True, timeout=420)
        except Exception as e:
            sys.stderr.write("[video] unduh gagal: %s\n" % e)
        finally:
            _vbusy.discard(vid)
            with LOCK:
                _vlocks.pop(vid, None)
    f = vcached_file(vid)
    if f:
        vprune()
    else:
        _vfail[vid] = time.time()
    return f


def video_async(vid):
    if vid in _vbusy or time.time() - _vfail.get(vid, 0) < 600:
        return
    _vbusy.add(vid)   # tandai dulu supaya permintaan berikutnya tidak membuat unduhan ganda
    def run():
        try:
            video_fetch(vid)
        finally:
            _vbusy.discard(vid)
    threading.Thread(target=run, daemon=True).start()
VID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
MIME = {".m4a": "audio/mp4", ".mp4": "audio/mp4", ".mp3": "audio/mpeg", ".webm": "audio/webm",
        ".opus": "audio/ogg", ".ogg": "audio/ogg"}
_dl_sem = threading.Semaphore(2)    # maksimal 2 unduhan sekaligus supaya HP server tidak berat
_warm_sem = threading.Semaphore(1)  # pemanasan di latar cuma boleh pakai 1 dari 2 slot unduhan, jadi lagu yang sedang diketuk tidak antre di belakangnya
_warming = set()                    # kunci lagu yang sedang dipanaskan (supaya tidak dobel)
_vid_locks = {}
_res_cache = {}                     # "judul|artis" -> (id video, durasi, judul YouTube)
_phase = {}                         # "judul|artis" -> "cari" (mencari di YouTube) / "muat" (file sudah ada di server) / "unduh" (sedang mengunduh)
_last_res = {}                      # uid -> waktu permintaan terakhir


def sign(vid, exp):
    return hmac.new(TOKEN.encode(), ("%s|%d" % (vid, exp)).encode(), hashlib.sha256).hexdigest()[:32]


def ck_args():
    try:
        return ["--cookies", YT_COOKIES] if os.path.getsize(YT_COOKIES) > 0 else []
    except OSError:
        return []


def cached_file(vid):
    for f in glob.glob(os.path.join(CACHE, vid + ".*")):
        if os.path.splitext(f)[1].lower() in MIME and os.path.getsize(f) > 0:
            return f
    return ""


def prune_cache():
    files = [f for f in glob.glob(os.path.join(CACHE, "*")) if os.path.isfile(f)]
    files.sort(key=lambda f: os.path.getmtime(f), reverse=True)
    for f in files[CACHE_KEEP:]:
        try:
            os.remove(f)
        except OSError:
            pass


def yt_pick(title, artist, ms):
    q = (title + " " + artist.split(",")[0]).strip()
    r = subprocess.run(["yt-dlp", "--no-playlist", "--no-warnings", "--flat-playlist", "--dump-single-json",
                        *ck_args(), "ytsearch6:" + q], capture_output=True, text=True, timeout=90)
    try:
        ents = [x for x in (json.loads(r.stdout).get("entries") or []) if x and VID_RE.match(str(x.get("id", "")))]
    except Exception:
        ents = []
    if not ents:
        raise RuntimeError("lagu tidak ketemu di server")
    toks = re.findall(r"\w+", q.lower())

    def score(x):
        hay = " ".join(str(x.get(k) or "") for k in ("title", "channel", "uploader")).lower()
        return sum(1 for t in toks if t in hay)
    pool = [x for x in ents if not x.get("duration") or x["duration"] <= YT_MAX] or ents
    top = max(score(x) for x in pool)
    cands = [x for x in pool if score(x) == top] if top > 0 else pool[:1]
    if ms and ms > 0:   # durasi paling mirip dengan lagu aslinya (menghindari versi live / remix panjang)
        best = min(cands, key=lambda x: abs((x.get("duration") or 10 ** 6) - ms / 1000.0))
    else:
        best = max(cands, key=lambda x: x.get("view_count") or 0)
    return best


def yt_fetch(vid):
    f = cached_file(vid)
    if f:
        os.utime(f)
        return f
    with LOCK:
        lk = _vid_locks.setdefault(vid, threading.Lock())
    with lk:
        f = cached_file(vid)
        if f:
            return f
        with _dl_sem:
            url = "https://www.youtube.com/watch?v=" + vid
            base = ["yt-dlp", "--no-playlist", "--no-warnings", *ck_args(), "-o", os.path.join(CACHE, "%(id)s.%(ext)s")]
            fallback = ["-x", "--audio-format", "mp3", "--audio-quality", "5"] if shutil.which("ffmpeg") else ["-f", "bestaudio"]
            for extra in (["-f", "bestaudio[ext=m4a]"], fallback):
                try:
                    subprocess.run(base + extra + [url], capture_output=True, timeout=240)
                except Exception as e:
                    sys.stderr.write("[yt] unduh gagal: %s\n" % e)
                f = cached_file(vid)
                if f:
                    break
        with LOCK:
            _vid_locks.pop(vid, None)
    if not f:
        raise RuntimeError("gagal menyiapkan audio")
    prune_cache()
    return f


def stream_info(vid, dur, ytitle):
    # e=0 -> alamat tidak pernah kedaluwarsa; keamanan tetap dari tanda tangan HMAC (tidak bisa dipalsukan tanpa token bot)
    return {"url": "api/stream?v=%s&e=0&s=%s" % (vid, sign(vid, 0)), "dur": dur, "yt": ytitle}


def resolve_fast(title, artist):
    """Jalur cepat: kalau lagu sudah pernah dicari DAN filenya masih ada di cache, jawab langsung (tanpa unduh, tanpa antre)."""
    key = (clean(title, 120) + "|" + clean(artist, 80).split(",")[0]).lower()
    with LOCK:
        c = _res_cache.get(key)
    f = cached_file(c[0]) if c else ""
    if f:
        try:
            os.utime(f)   # tandai baru dipakai, supaya lagu yang sering diputar tidak ikut terhapus saat cache dibersihkan
        except OSError:
            pass
        return stream_info(c[0], c[1], c[2])
    return None


def res_key(title, artist):
    return (clean(title, 120) + "|" + clean(artist, 80).split(",")[0]).lower()


def resolve(title, artist, ms):
    key = res_key(title, artist)
    try:
        with LOCK:
            c = _res_cache.get(key)
        if c and cached_file(c[0]):
            vid, dur, ytitle = c
        else:
            _phase[key] = "cari"
            best = yt_pick(clean(title, 120), clean(artist, 80), ms)
            vid, dur, ytitle = best["id"], int(best.get("duration") or 0), str(best.get("title") or "")
            if dur and dur > YT_MAX:
                raise RuntimeError("video terlalu panjang (%d menit)" % (dur // 60))
            with LOCK:
                if len(_res_cache) > 300:
                    _res_cache.clear()
                _res_cache[key] = (vid, dur, ytitle)
        # inilah penentunya: file lagu ada di server -> cuma dimuat; tidak ada -> diunduh dulu
        _phase[key] = "muat" if cached_file(vid) else "unduh"
        yt_fetch(vid)
        return stream_info(vid, dur, ytitle)
    finally:
        _phase.pop(key, None)


# ---------------------------------------------------------------- lirik untuk kartu lagu di Mini App (sumber: lrclib.net)
_lyr_cache = {}


def parse_lrc(t):
    out = []
    for ln in (t or "").splitlines():
        ln = ln.strip()
        e = ln.find("]")
        if not ln.startswith("[") or e < 0 or ":" not in ln[1:e]:
            continue
        m, sec = ln[1:e].split(":", 1)
        try:
            v = int(m) * 60 + float(sec)
        except ValueError:
            continue
        out.append([round(v, 2), ln[e + 1:].strip()[:200]])
    return out


def get_lyrics(title, artist, ms):
    a1 = artist.split(",")[0].strip()
    key = (title.lower(), a1.lower())
    with LOCK:
        if key in _lyr_cache:
            return _lyr_cache[key]
    cands, failed = [], False
    for params in ({"track_name": title, "artist_name": a1}, {"q": (title + " " + a1).strip()}):
        try:
            req = urllib.request.Request("https://lrclib.net/api/search?" + urllib.parse.urlencode(params),
                                         headers={"User-Agent": "TelegramBotMiniApp/1.0"})
            with urllib.request.urlopen(req, timeout=8) as r:
                data = json.loads(r.read().decode("utf-8", "replace"))
            cands = [x for x in data if isinstance(x, dict)] if isinstance(data, list) else []
        except Exception as e:
            sys.stderr.write("[lirik] gagal: %s\n" % e)
            failed, cands = True, []
        if cands:
            break

    def gap(x):
        d = x.get("duration") or 0
        return abs(d - ms / 1000.0) if ms and d else 0
    if ms:   # buang lirik yang durasinya jauh beda (versi lain), supaya waktunya tidak meleset
        cands = [x for x in cands if gap(x) <= 25]
    pool = [x for x in cands if x.get("syncedLyrics")] or [x for x in cands if x.get("plainLyrics")]
    res = {"synced": False, "lines": []}
    if pool:
        best = min(pool, key=gap)
        lines = parse_lrc(best.get("syncedLyrics")) if best.get("syncedLyrics") else []
        if lines:
            res = {"synced": True, "lines": lines[:400]}
        else:
            plain = [[-1, x.strip()[:200]] for x in (best.get("plainLyrics") or "").splitlines()]
            res = {"synced": False, "lines": plain[:400]}
    if not failed:   # kegagalan jaringan tidak disimpan, supaya dicoba lagi lain kali
        with LOCK:
            if len(_lyr_cache) > 200:
                _lyr_cache.clear()
            _lyr_cache[key] = res
    return res


def warm_async(title, artist, ms):
    """Siapkan lagu (cari di YouTube + unduh ke cache) di latar belakang, begitu lagu masuk playlist.
    Saat lagu diputar nanti, resolve() tinggal ambil dari cache -> langsung jalan, tanpa nunggu menyiapkan."""
    key = (clean(title, 120) + "|" + clean(artist, 80).split(",")[0]).lower()
    with LOCK:
        if key in _warming:
            return
        _warming.add(key)

    def job():
        try:
            if resolve_fast(title, artist):
                return
            with _warm_sem:
                resolve(clean(title, 120), clean(artist, 80), ms)
        except Exception as e:
            sys.stderr.write("[warm] gagal: %s\n" % e)
        finally:
            with LOCK:
                _warming.discard(key)
    threading.Thread(target=job, daemon=True).start()


# ---------------------------------------------------------------- playlist Mini App (disimpan per pengguna di ~/.spotify_pl_<id>.json)
PL_PREFIX = E.get("SPOTIFY_PL_PREFIX", HOME + "/.spotify_pl_")


def pl_path(uid):
    return "%s%s.json" % (PL_PREFIX, re.sub(r"[^0-9-]", "", str(uid)))


def pl_load(uid):
    try:
        with open(pl_path(uid), encoding="utf-8") as f:
            d = json.load(f)
    except Exception:
        d = {}
    for k, v in (("items", []), ("order", []), ("pos", -1), ("playing", False),
                 ("mode", "urut"), ("loop", False), ("mid", 0), ("next_at", 0)):
        d.setdefault(k, v)
    return d


def pl_save(uid, d):
    f = pl_path(uid)
    with open(f + ".tmp", "w", encoding="utf-8") as fh:
        json.dump(d, fh, ensure_ascii=False)
    os.replace(f + ".tmp", f)


def pl_api(kind, uid, body):
    with LOCK:
        d = pl_load(uid)
        if kind == "get":
            return {"items": d["items"]}
        if kind == "add":
            title, artist = clean(body.get("title", ""), 120), clean(body.get("artist", ""), 80)
            if not title:
                raise ValueError("judul kosong")
            key = (title.lower(), artist.lower())
            if any((x.get("title", "").lower(), x.get("artist", "").lower()) == key for x in d["items"]):
                return {"dup": True, "total": len(d["items"])}
            cover = body.get("cover", "")
            if not (isinstance(cover, str) and cover.startswith("https://") and len(cover) < 400):
                cover = ""
            try:
                ms = max(0, int(body.get("ms") or 0))
            except (TypeError, ValueError):
                ms = 0
            d["items"].append({"title": title, "artist": artist, "ms": ms, "cover": cover})
            n = len(d["items"]) - 1
            if len(d["order"]) == n:
                d["order"].append(n)
            else:
                d["order"] = list(range(n + 1))
                if not d["playing"]:
                    d["pos"] = -1
            pl_save(uid, d)
            return {"ok": True, "total": len(d["items"])}
        if kind == "del":
            try:
                i = int(body.get("i"))
            except (TypeError, ValueError):
                raise ValueError("nomor tidak valid")
            if not 0 <= i < len(d["items"]):
                raise ValueError("lagu tidak ada")
            d["items"].pop(i)
            if i in d["order"] and d["order"].index(i) <= d["pos"]:
                d["pos"] -= 1
            d["order"] = [x if x < i else x - 1 for x in d["order"] if x != i]
            if not d["items"]:
                d.update({"order": [], "pos": -1, "playing": False, "next_at": 0})
            pl_save(uid, d)
            return {"ok": True, "total": len(d["items"])}
        if kind == "clear":
            d.update({"items": [], "order": [], "pos": -1, "playing": False, "next_at": 0})
            pl_save(uid, d)
            return {"ok": True, "total": 0}
    raise ValueError("aksi tidak dikenal")


# ---------------------------------------------------------------- game Tic Tac Toe (lawan teman)
TTT_LINES = [(0,1,2),(3,4,5),(6,7,8),(0,3,6),(1,4,7),(2,5,8),(0,4,8),(2,4,6)]
WEBAPP_URL = E.get("SPOTIFY_WEBAPP_URL", "").rstrip("/")
VISITORS = E.get("VISITORS_FILE", HOME + "/.telegram_visitors")
NAMECACHE = E.get("NAME_CACHE_FILE", HOME + "/.telegram_name_cache")
GLOCK = threading.Lock()
GAMES = {}        # id game -> dict (hanya di memori, dibuang setelah 6 jam tak dipakai)
_names = {}       # uid -> nama
_last_inv = {}    # uid -> waktu undangan terakhir (batas laju)


def name_of(uid, hint=""):
    uid = str(uid)
    if hint:
        _names[uid] = hint
    if uid in _names:
        return _names[uid]
    nm = ""
    for fn, ci in ((VISITORS, 2), (NAMECACHE, 1)):
        try:
            for line in open(fn, encoding="utf-8"):
                c = line.rstrip("\n").split("\t")
                if c and c[0] == uid and len(c) > ci and c[ci].strip():
                    nm = c[ci].strip()
                    break
        except OSError:
            pass
        if nm:
            break
    if not nm:
        try:
            j = http_json("%s/bot%s/getChat?chat_id=%s" % (TG_API, TOKEN, urllib.parse.quote(uid)))
            r = j.get("result") or {}
            nm = " ".join(x for x in (r.get("first_name"), r.get("last_name")) if x).strip() or (("@" + r["username"]) if r.get("username") else "")
        except Exception:
            nm = ""
    nm = re.sub(r"\s+", " ", nm).strip()[:30] or ("ID " + uid)
    _names[uid] = nm
    return nm


def user_name(u):
    n = " ".join(x for x in (u.get("first_name"), u.get("last_name")) if x).strip() or (("@" + u["username"]) if u.get("username") else "")
    return name_of(u["id"], re.sub(r"\s+", " ", n).strip()[:30])


def registered_ids():
    ids = {OWNER}
    try:
        for l in open(EXTRA_IDS, encoding="utf-8"):
            l = l.strip()
            if re.match(r"^-?\d+$", l):
                ids.add(l)
    except OSError:
        pass
    return [i for i in ids if allowed(i)]


def tg_send(chat, text, btn=None, url=None):
    def run():
        try:
            body = {"chat_id": int(chat), "text": text}
            if btn and url:
                body["reply_markup"] = {"inline_keyboard": [[{"text": btn, "web_app": {"url": url}}]]}
            req = urllib.request.Request("%s/bot%s/sendMessage" % (TG_API, TOKEN), json.dumps(body).encode("utf-8"),
                                         {"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=20).read()
        except Exception as e:
            sys.stderr.write("[ttt] kirim undangan gagal: %s\n" % e)
    threading.Thread(target=run, daemon=True).start()


TTT_NEXT_DELAY = 2.8   # detik papan akhir ditahan (animasi menang/kalah ~2,3 dtk) sebelum ronde berikutnya otomatis mulai


def ttt_autonext(g):
    t = g.get("over_at")
    if t and time.time() - t >= TTT_NEXT_DELAY:
        w, _ = ttt_winner(g["b"])
        g["last"] = {"res": w or "", "rid": g.get("n", 0), "t": time.time()}
        g["b"] = [""] * 9
        g["starter"] = "O" if g["starter"] == "X" else "X"
        g["turn"] = g["starter"]
        g["over_at"] = None


def ttt_winner(b):
    for l in TTT_LINES:
        if b[l[0]] and b[l[0]] == b[l[1]] == b[l[2]]:
            return b[l[0]], list(l)
    return ("D", []) if all(b) else (None, [])


def ttt_purge():
    now = time.time()
    for k in [k for k, g in GAMES.items() if now - g["ts"] > 21600]:
        del GAMES[k]


def ttt_view(g, uid):
    ttt_autonext(g)
    me = "X" if uid == g["x"] else "O"
    opp = g["o"] if me == "X" else g["x"]
    w, line = ttt_winner(g["b"])
    return {"id": g["id"], "me": me, "opp": name_of(opp), "b": g["b"], "turn": g["turn"],
            "over": bool(w), "res": w or "", "line": line, "joined": g["joined"],
            "score": g["score"], "rid": g.get("n", 0),
            "last": ({"res": g["last"]["res"], "rid": g["last"]["rid"]} if g.get("last") and time.time() - g["last"]["t"] < 8 else None)}


def ttt_get_game(gid, uid):
    g = GAMES.get(gid)
    if not g or uid not in (g["x"], g["o"]):
        return None
    g["ts"] = time.time()
    return g


def ttt_api(kind, u, d):
    """Kembalikan (kode, isi). kind: players | invite | state | move | round | reset"""
    uid = str(u["id"])
    user_name(u)
    with GLOCK:
        ttt_purge()
        if kind == "players":
            pl = sorted(({"id": i, "name": name_of(i)} for i in registered_ids() if i != uid), key=lambda x: x["name"].lower())
            gl = [{"id": g["id"], "opp": name_of(g["o"] if uid == g["x"] else g["x"]), "joined": g["joined"],
                   "mine": g["joined"] and g["turn"] == ("X" if uid == g["x"] else "O")}
                  for g in GAMES.values() if uid in (g["x"], g["o"])]
            return 200, {"players": pl, "games": gl}
        if kind == "invite":
            to = str(d.get("to", ""))
            if to == uid or to not in registered_ids():
                return 400, {"error": "Teman itu tidak terdaftar di bot."}
            for g in GAMES.values():
                if {g["x"], g["o"]} == {uid, to}:
                    return 200, ttt_view(g, uid)    # permainan dengan orang yang sama dilanjutkan
            now = time.time()
            if now - _last_inv.get(uid, 0) < 5:
                return 429, {"error": "Pelan-pelan, tunggu sebentar."}
            _last_inv[uid] = now
            if len(GAMES) >= 200:
                return 503, {"error": "Terlalu banyak permainan aktif, coba lagi nanti."}
            gid = "%08x" % int.from_bytes(os.urandom(4), "big")
            g = {"id": gid, "x": uid, "o": to, "b": [""] * 9, "turn": "X", "starter": "X", "joined": False,
                 "score": {"x": 0, "o": 0, "d": 0}, "ts": now}
            GAMES[gid] = g
            if WEBAPP_URL:
                tg_send(to, "🎮 %s mengajakmu main Tic Tac Toe!" % user_name(u), "🎮 Terima & Main", "%s/ttt?g=%s" % (WEBAPP_URL, gid))
            return 200, ttt_view(g, uid)
        g = ttt_get_game(str(d.get("g", "")), uid)
        if not g:
            return 404, {"error": "Permainan sudah berakhir atau tidak ditemukan."}
        ttt_autonext(g)
        if kind == "state":
            if uid == g["o"]:
                g["joined"] = True
        elif kind == "move":
            try:
                c = int(d.get("c"))
            except (TypeError, ValueError):
                c = -1
            me = "X" if uid == g["x"] else "O"
            w, _ = ttt_winner(g["b"])
            if g["joined"] and not w and g["turn"] == me and 0 <= c < 9 and not g["b"][c]:
                g["b"][c] = me
                w, _ = ttt_winner(g["b"])
                if w:
                    g["score"][{"X": "x", "O": "o", "D": "d"}[w]] += 1
                    g["n"] = g.get("n", 0) + 1     # nomor ronde yang baru selesai (dipakai klien supaya animasi tidak diputar dua kali)
                    g["over_at"] = time.time()     # papan akhir ditahan TTT_NEXT_DELAY detik, lalu ttt_autonext memulai ronde baru
                else:
                    g["turn"] = "O" if me == "X" else "X"
        elif kind in ("round", "reset"):
            if kind == "reset":
                g["score"] = {"x": 0, "o": 0, "d": 0}
            g["b"] = [""] * 9
            g["starter"] = "O" if g["starter"] == "X" else "X"
            g["turn"] = g["starter"]
            g["last"] = None
            g["over_at"] = None
        return 200, ttt_view(g, uid)


TTT_HTML = r"""<!doctype html>
<html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<title>Tic Tac Toe</title>
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<style>
:root{--bg:#0d0a1f;--x:#ff5c93;--o:#38d6ff;--gold:#ffd54a;--mu:#a49fc4;--tx:#f3f1ff;--glass:rgba(255,255,255,.06);--gl2:rgba(255,255,255,.10);--bd:rgba(255,255,255,.12)}
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
html,body{margin:0;min-height:100%;background:var(--bg);color:var(--tx);font-family:-apple-system,"Segoe UI",Roboto,"Helvetica Neue",sans-serif}
body{min-height:100vh;display:flex;align-items:center;justify-content:center;padding:16px;position:relative;overflow-x:hidden;
 background:radial-gradient(60% 40% at 0% 0%,rgba(255,92,147,.30),rgba(255,92,147,0) 70%),radial-gradient(70% 45% at 100% 100%,rgba(56,214,255,.28),rgba(56,214,255,0) 70%),radial-gradient(120% 80% at 50% -10%,#2a1b5e 0%,rgba(42,27,94,0) 60%),var(--bg)}
.orb{display:none}
.card{position:relative;z-index:1;overflow:hidden;width:100%;max-width:380px;border-radius:28px;padding:20px 18px 18px;
 background:linear-gradient(160deg,rgba(255,255,255,.11),rgba(255,255,255,.04));border:1px solid var(--bd);
 box-shadow:0 12px 32px rgba(0,0,0,.45),inset 0 1px 0 rgba(255,255,255,.15)}
/* menu */
.mn{display:flex;flex-direction:column;gap:12px}
.hero{text-align:center;margin-bottom:6px}
.logo{display:grid;grid-template-columns:repeat(3,1fr);gap:6px;width:108px;margin:2px auto 12px}
.logo i{aspect-ratio:1;border-radius:10px;background:var(--glass);border:1px solid var(--bd);display:flex;align-items:center;justify-content:center}
.logo svg{width:70%;height:70%}
.hero h1{margin:0;font-size:28px;font-weight:800;letter-spacing:.5px;background:linear-gradient(90deg,var(--x),#ffb36b 45%,var(--o));-webkit-background-clip:text;background-clip:text;color:transparent;-webkit-text-fill-color:transparent}
.hero p{margin:4px 0 0;color:var(--mu);font-size:13px}
.big{display:flex;align-items:center;gap:14px;width:100%;text-align:left;padding:14px 16px;border-radius:20px;border:1px solid var(--bd);background:var(--glass);color:var(--tx);font-family:inherit;transition:transform .12s,background .2s}
.big:active{transform:scale(.97)}
.big .ic{width:46px;height:46px;border-radius:14px;display:flex;align-items:center;justify-content:center;font-size:24px;background:var(--gl2);flex:none}
.big b{display:block;font-size:16px;font-weight:700}
.big small{display:block;color:var(--mu);font-size:12px;margin-top:2px}
.big.p{background:linear-gradient(120deg,rgba(255,92,147,.9),rgba(255,140,90,.85));border-color:rgba(255,255,255,.25);box-shadow:0 10px 28px -8px rgba(255,92,147,.7)}
.big.p .ic{background:rgba(255,255,255,.22)}.big.p small{color:rgba(255,255,255,.85)}
.big.q{background:linear-gradient(120deg,rgba(56,214,255,.22),rgba(110,90,255,.28))}
.sec{color:var(--mu);font-size:11px;margin:12px 4px 2px;letter-spacing:1.2px;font-weight:700}
.row{display:flex;align-items:center;gap:10px;background:var(--glass);border:1px solid var(--bd);border-radius:16px;padding:8px 8px 8px 8px;margin-top:8px}
.av{width:36px;height:36px;border-radius:50%;flex:none;display:flex;align-items:center;justify-content:center;font-weight:800;font-size:15px;color:#fff;background:linear-gradient(135deg,var(--x),var(--o))}
.row span{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:14px;font-weight:600}
.row button{height:34px;border-radius:17px;border:0;background:linear-gradient(120deg,var(--x),#ff8a5c);color:#fff;font-weight:700;font-size:13px;padding:0 16px;font-family:inherit}
.row i{font-style:normal;color:var(--gold);font-size:11px;font-weight:700}
.tp{display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;color:var(--mu);font-size:13px;font-weight:600}
.tp button{border:1px solid var(--bd);background:var(--glass);color:var(--tx);font-size:13px;padding:6px 12px;border-radius:14px;font-family:inherit}
.vs{text-align:center;color:var(--mu);font-size:12px;margin:-4px 0 10px}
/* status */
.st{text-align:center;font-size:15px;font-weight:600;min-height:38px;line-height:38px;margin-bottom:12px;border-radius:19px;background:var(--glass);border:1px solid var(--bd);color:var(--tx);padding:0 12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.st.win{color:#1b1400;background:linear-gradient(120deg,#ffe27a,#ffb83d);border-color:transparent;box-shadow:0 6px 22px -6px rgba(255,200,0,.7)}
.st.lose{color:#fff;background:linear-gradient(120deg,#ff5a5f,#c2185b);border-color:transparent;box-shadow:0 6px 22px -6px rgba(255,60,80,.6)}
/* board */
.grid{position:relative;display:grid;grid-template-columns:repeat(3,1fr);gap:10px}
.c{aspect-ratio:1;border-radius:18px;background:#1c1a34;border:1px solid var(--bd);display:flex;align-items:center;justify-content:center;padding:0;font-family:inherit;color:#fff;touch-action:manipulation;transition:transform .08s}
.c:active:not(:disabled){transform:scale(.93)}
.c:not(:disabled):not(.x):not(.o){border-color:rgba(255,255,255,.2)}
.c svg{width:68%;height:68%;overflow:visible}
.c svg *{fill:none;stroke:currentColor;stroke-width:11;stroke-linecap:round}
.c.x{color:var(--x)}.c.o{color:var(--o)}
.c.w{border-color:currentColor;background:#2a2750}
.c:disabled{cursor:default}
.wl{position:absolute;left:0;top:0;width:100%;height:100%;pointer-events:none;overflow:visible;z-index:3}
.wl line{stroke-width:7;stroke-linecap:round}
/* skor */
.sb{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin-top:14px}
.pl{--ac:var(--mu);text-align:center;border-radius:16px;padding:8px 4px 8px;background:var(--glass);border:1px solid var(--bd);border-top:3px solid var(--ac);min-width:0}
.pl small{display:block;color:var(--mu);font-size:11px;font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.pl b{display:block;font-size:24px;font-weight:800;color:var(--ac);line-height:1.2}
.bt{display:flex;gap:10px;margin-top:12px}
.bt button{flex:1;height:44px;border-radius:22px;font-size:14px;font-weight:700;font-family:inherit;border:1px solid var(--bd);background:var(--glass);color:var(--tx)}
.bt button.p{background:linear-gradient(120deg,rgba(56,214,255,.85),rgba(110,90,255,.9));border-color:transparent}
.bt button:active{opacity:.8}
/* efek menang/kalah/seri: keadaan dasar SUDAH terlihat (tidak bergantung pada animasi CSS) */
.fx{position:absolute;left:0;right:0;top:0;bottom:0;z-index:20;pointer-events:none;overflow:hidden;border-radius:28px}
.fx .fl{position:absolute;left:0;right:0;top:0;bottom:0}
.fx.win .fl{background:radial-gradient(circle at 50% 45%,rgba(255,213,74,.5),rgba(255,213,74,0) 70%)}
.fx.lose .fl{background:radial-gradient(circle at 50% 45%,rgba(255,59,48,.45),rgba(20,0,10,.35) 85%)}
.fx.draw .fl{background:radial-gradient(circle at 50% 45%,rgba(164,159,196,.38),rgba(164,159,196,0) 70%)}
.fx .bn{position:absolute;left:0;right:0;top:50%;margin-top:-70px;text-align:center;font-weight:900;white-space:nowrap}
.fx .bn i{display:block;font-style:normal;font-size:80px;line-height:1.1}
.fx .bn b{display:block;font-size:42px;letter-spacing:3px}
.fx.win .bn{color:var(--gold);text-shadow:0 4px 28px rgba(255,200,0,.75)}
.fx.lose .bn{color:#ff7a70;text-shadow:0 4px 28px rgba(255,40,30,.6)}
.fx.draw .bn{color:#e3e0f7;text-shadow:0 4px 24px rgba(164,159,196,.6)}
.fx .p{position:absolute;top:-24px;width:9px;height:14px;opacity:0}
.fx.lose .p{width:auto;height:auto;font-size:17px}
.big.l1{background:linear-gradient(120deg,rgba(74,222,128,.26),rgba(34,197,94,.16))}
.big.l2{background:linear-gradient(120deg,rgba(56,214,255,.26),rgba(110,90,255,.22))}
.big.l3{background:linear-gradient(120deg,rgba(255,170,60,.32),rgba(255,110,60,.22))}
.big.l4{background:linear-gradient(120deg,rgba(255,59,48,.42),rgba(160,20,90,.32));border-color:rgba(255,120,100,.55)}
.big small.rc{opacity:.8;margin-top:3px;font-size:11px}
.big .lvs{margin-left:auto;font-size:12px;letter-spacing:1px;font-weight:800;opacity:.95;white-space:nowrap}
.hide{display:none!important}
</style></head>
<body>
<div class="orb o1"></div><div class="orb o2"></div>
<div class="card">
  <div class="fx hide" id="fx"></div>
  <div id="menu" class="mn">
    <div class="hero">
      <div class="logo" id="logo"></div>
      <h1>TIC TAC TOE</h1>
      <p>Tiga sejajar, kamu menang!</p>
    </div>
    <button class="big p" id="mb"><span class="ic">🤖</span><span><b>Lawan Bot</b><small>4 tingkat: Mudah sampai Mustahil, skor tersimpan</small></span></button>
    <button class="big q" id="mf"><span class="ic">👥</span><span><b>Main dengan Teman</b><small>Undang teman lewat bot</small></span></button>
  </div>
  <div id="fr" class="mn hide">
    <div class="tp"><button id="fb">← Kembali</button><span>Pilih teman</span></div>
    <div id="fl"></div>
  </div>
  <div id="df" class="mn hide">
    <div class="tp"><button id="db">← Kembali</button><span>Pilih tingkat kesulitan</span></div>
    <button class="big l1" data-lv="1"><span class="ic">😴</span><span><b>Mudah</b><small>Bot main asal-asalan, gampang dikalahkan</small><small class="rc" id="rc1"></small></span><span class="lvs">★☆☆☆</span></button>
    <button class="big l2" data-lv="2"><span class="ic">🙂</span><span><b>Sedang</b><small>Kadang menutup dan menyerang, masih sering salah</small><small class="rc" id="rc2"></small></span><span class="lvs">★★☆☆</span></button>
    <button class="big l3" data-lv="3"><span class="ic">😤</span><span><b>Sulit</b><small>Selalu menutup dan menyerang, jarang salah</small><small class="rc" id="rc3"></small></span><span class="lvs">★★★☆</span></button>
    <button class="big l4" data-lv="4"><span class="ic">👑</span><span><b>Mustahil</b><small>Sempurna 100%, tidak mungkin kalah</small><small class="rc" id="rc4"></small></span><span class="lvs">★★★★</span></button>
  </div>
  <div id="gm" class="hide">
    <div class="tp"><button id="gb">← Menu</button><span id="mode"></span></div>
    <div class="vs" id="vs"></div>
    <div class="st" id="st">Giliran kamu</div>
    <div class="grid" id="g"></div>
    <div class="sb">
      <div class="pl" id="pl1" style="--ac:var(--x)"><small id="l1">Kamu</small><b id="sx">0</b></div>
      <div class="pl"><small>Seri</small><b id="sd" style="color:var(--tx)">0</b></div>
      <div class="pl" id="pl2" style="--ac:var(--o)"><small id="l2">Bot</small><b id="so">0</b></div>
    </div>
    <div class="bt"><button id="rr">Ulang ronde</button><button id="rs" class="p">Reset skor</button></div>
  </div>
</div>
<script>
(function () {
var tg = window.Telegram && window.Telegram.WebApp;
try { if (tg) { tg.ready(); tg.expand(); try { tg.setHeaderColor("#0d0a1f"); tg.setBackgroundColor("#0d0a1f"); } catch (e1) {} } } catch (e) {}
function hap() { try { tg.HapticFeedback.impactOccurred("light"); } catch (e) {} }
function $(i) { return document.getElementById(i); }
// animasi lewat Web Animations API; kalau tidak didukung / gagal, elemen tetap tampil statis (tidak pernah hilang)
function anim(el, kf, opt) { try { if (el && el.animate) return el.animate(kf, opt); } catch (e) {} return null; }
var INIT = (tg && tg.initData) || "";
var L = [[0,1,2],[3,4,5],[6,7,8],[0,3,6],[1,4,7],[2,5,8],[0,4,8],[2,4,6]];
var mode = "menu", b = ["", "", "", "", "", "", "", "", ""], over = false, busy = false, wl = [];
var sc = {x: 0, o: 0, d: 0}, bsc = {x: 0, o: 0, d: 0};
var net = null, gid = "", timer = null, animRid = -1, hold = null;
var ANIM_MS = 2300, animT = null;
var LV = 3, NAMES = {1: "Mudah", 2: "Sedang", 3: "Sulit", 4: "Mustahil"}, bscs = {};
function blank() { return {x: 0, o: 0, d: 0}; }
try {
  var s2 = JSON.parse(localStorage.getItem("ttt_score2") || "null");
  if (s2 && typeof s2 === "object") bscs = s2;
  else { var s0 = JSON.parse(localStorage.getItem("ttt_score") || "null"); if (s0 && typeof s0.x === "number") bscs = {3: s0}; }   // skor lama dianggap level Sulit
} catch (e) {}
for (var q = 1; q <= 4; q++) if (!bscs[q] || typeof bscs[q].x !== "number") bscs[q] = blank();
bsc = bscs[LV];
function save() { try { localStorage.setItem("ttt_score2", JSON.stringify(bscs)); } catch (e) {} }
function show(v) { ["menu", "fr", "df", "gm"].forEach(function (k) { $(k).classList.toggle("hide", k !== v); }); }
// ---- tanda X / O sebagai SVG (kondisi dasar sudah tergambar penuh)
function markSVG(v) {
  if (v === "X") return '<svg viewBox="0 0 100 100"><path pathLength="1" d="M26 26L74 74"/><path pathLength="1" d="M74 26L26 74"/></svg>';
  return '<svg viewBox="0 0 100 100"><circle pathLength="1" cx="50" cy="50" r="25" transform="rotate(-90 50 50)"/></svg>';
}
(function () {
  var lg = $("logo"), seq = ["X", "", "O", "", "X", "", "O", "", "X"];
  seq.forEach(function (v, k) {
    var i = document.createElement("i"); if (v) { i.style.color = v === "X" ? "var(--x)" : "var(--o)"; i.innerHTML = markSVG(v); var s = i.firstChild; var ch = s.querySelectorAll("*"); for (var z = 0; z < ch.length; z++) { ch[z].setAttribute("fill", "none"); ch[z].setAttribute("stroke", "currentColor"); ch[z].setAttribute("stroke-width", "12"); ch[z].setAttribute("stroke-linecap", "round"); } }
    lg.appendChild(i);
  });
})();
function win(a) {
  for (var i = 0; i < L.length; i++) { var l = L[i]; if (a[l[0]] && a[l[0]] === a[l[1]] && a[l[1]] === a[l[2]]) return {w: a[l[0]], l: l}; }
  for (var j = 0; j < 9; j++) if (!a[j]) return null;
  return {w: "D", l: []};
}
var MEMO = {};
function mm(a, t, d) {
  var key = a.map(function (c) { return c || "-"; }).join("") + t + d; if (MEMO[key] !== undefined) return MEMO[key];   // sel kosong ditandai agar posisi tidak tertukar
  var res = mm0(a, t, d); MEMO[key] = res; return res;
}
function mm0(a, t, d) {
  var r = win(a);
  if (r) return r.w === "O" ? 10 - d : r.w === "X" ? d - 10 : 0;
  var best = null;
  for (var i = 0; i < 9; i++) if (!a[i]) {
    a[i] = t; var v = mm(a, t === "O" ? "X" : "O", d + 1); a[i] = "";
    if (best === null || (t === "O" && v > best) || (t === "X" && v < best)) best = v;
  }
  return best;
}
function pick(arr) { return arr[Math.floor(Math.random() * arr.length)]; }
function lineMove(p) {   // sel kosong yang melengkapi 3 sejajar untuk pemain p, atau -1
  for (var k = 0; k < L.length; k++) {
    var l = L[k], c = 0, e = -1;
    for (var j = 0; j < 3; j++) { if (b[l[j]] === p) c++; else if (!b[l[j]]) e = l[j]; }
    if (c === 2 && e >= 0) return e;
  }
  return -1;
}
function bestMove(free) {   // minimax penuh: tidak pernah kalah, secepat mungkin menang
  var top = -99, sc2 = [], i;
  for (i = 0; i < free.length; i++) { b[free[i]] = "O"; var v = mm(b, "X", 1); b[free[i]] = ""; sc2.push([v, free[i]]); if (v > top) top = v; }
  return pick(sc2.filter(function (p) { return p[0] === top; }).map(function (p) { return p[1]; }));
}
function botMove() {
  var free = [], i;
  for (i = 0; i < 9; i++) if (!b[i]) free.push(i);
  var win1 = lineMove("O"), blk = lineMove("X");
  if (LV === 1) return (win1 >= 0 && Math.random() < .25) ? win1 : pick(free);               // Mudah: asal jalan, sesekali kebetulan menang
  if (LV === 2) {                                                                              // Sedang: sering lupa menutup
    if (win1 >= 0 && Math.random() < .8) return win1;
    if (blk >= 0 && Math.random() < .55) return blk;
    return pick(free);
  }
  if (LV === 3) {                                                                              // Sulit: taktik selalu benar, strategi kadang meleset
    if (win1 >= 0) return win1;
    if (blk >= 0) return blk;
    return Math.random() < .8 ? bestMove(free) : pick(free);
  }
  return bestMove(free);                                                                       // Mustahil: sempurna
}
var g = $("g"), st = $("st"), cells = [], shown = ["", "", "", "", "", "", "", "", ""], lineKey = "";
function haptic(kind) {
  try { tg.HapticFeedback.notificationOccurred(kind === "win" ? "success" : kind === "lose" ? "error" : "warning"); }
  catch (e) { try { if (navigator.vibrate) navigator.vibrate(kind === "lose" ? [90, 50, 90] : 60); } catch (e2) {} }
}
function stopAnim() {
  clearTimeout(animT); var f = $("fx"); f.className = "fx hide"; f.textContent = "";
}
function playAnim(kind) {   // kind: win | lose | draw
  stopAnim();
  var f = $("fx"), fl = document.createElement("div"), bn = document.createElement("div"), ic = document.createElement("i"), tx = document.createElement("b");
  fl.className = "fl";
  ic.textContent = kind === "win" ? "🏆" : kind === "lose" ? "💔" : "🤝";
  tx.textContent = kind === "win" ? "MENANG!" : kind === "lose" ? "KALAH" : "SERI";
  bn.className = "bn"; bn.appendChild(ic); bn.appendChild(tx);
  f.className = "fx " + kind; f.appendChild(fl); f.appendChild(bn);   // sudah terlihat penuh tanpa animasi
  anim(fl, [{opacity: 0}, {opacity: 1, offset: .2}, {opacity: .8}], {duration: 700, easing: "ease-out"});
  if (kind === "lose") anim(bn, [{transform: "translateY(-120px) scale(1.5)", opacity: 0}, {transform: "translateY(0) scale(1)", opacity: 1}], {duration: 550, easing: "cubic-bezier(.3,1.4,.5,1)"});
  else anim(bn, [{transform: "scale(0) rotate(-14deg)", opacity: 0}, {transform: "scale(1) rotate(0deg)", opacity: 1}], {duration: 600, easing: "cubic-bezier(.2,1.7,.4,1)"});
  if (kind === "win") anim(ic, [{transform: "rotate(-10deg) scale(1)"}, {transform: "rotate(10deg) scale(1.12)"}, {transform: "rotate(-10deg) scale(1)"}], {duration: 900, iterations: 2, easing: "ease-in-out"});
  var cols = ["#ffd54a", "#ff6b81", "#4cd964", "#5ac8fa", "#af52de", "#ff9f0a"], n = kind === "draw" ? 0 : 22;
  for (var i = 0; i < n; i++) {
    var p = document.createElement("div"); p.className = "p";
    p.style.left = (Math.random() * 100) + "%";
    if (kind === "win") { p.style.background = cols[i % cols.length]; p.style.borderRadius = i % 3 === 0 ? "50%" : "2px"; }
    else p.textContent = "💧";
    f.appendChild(p);
    var dist = (f.offsetHeight || 520) + 40, rot = kind === "win" ? 760 : 0;
    var a = anim(p, [{transform: "translateY(0) rotate(0deg)", opacity: 1}, {transform: "translateY(" + dist + "px) rotate(" + rot + "deg)", opacity: .9}], {duration: 1100 + Math.random() * 1100, delay: Math.random() * 450, easing: "linear", fill: "both"});
    if (!a) p.style.display = "none";
  }
  // papan: getar saat kalah, denyut sel pemenang
  if (kind === "lose") anim(g, [{transform: "translateX(0)"}, {transform: "translateX(-10px)"}, {transform: "translateX(9px)"}, {transform: "translateX(-7px)"}, {transform: "translateX(6px)"}, {transform: "translateX(0)"}], {duration: 600, easing: "ease-in-out"});
  for (var k = 0; k < wl.length; k++) anim(cells[wl[k]], [{transform: "scale(1)"}, {transform: "scale(1.12)"}, {transform: "scale(1)"}], {duration: 550, iterations: 4, easing: "ease-in-out"});
  haptic(kind);
  animT = setTimeout(stopAnim, ANIM_MS);
}
for (var i = 0; i < 9; i++) {
  (function (i) {
    var c = document.createElement("button"); c.className = "c"; c.addEventListener("pointerdown", function (ev) { ev.preventDefault(); play(i); });
    g.appendChild(c); cells.push(c);
  })(i);
}
// garis kemenangan (SVG) di atas papan
function drawLine() {
  var old = g.querySelector(".wl"), key = wl.length === 3 ? wl.join(",") : "";
  if (key === lineKey && (!key || old)) return;
  lineKey = key;
  if (old) g.removeChild(old);
  if (!key) return;
  var a = cells[wl[0]], z = cells[wl[2]];
  var ax = a.offsetLeft + a.offsetWidth / 2, ay = a.offsetTop + a.offsetHeight / 2, zx = z.offsetLeft + z.offsetWidth / 2, zy = z.offsetTop + z.offsetHeight / 2;
  var dx = zx - ax, dy = zy - ay, ln = Math.sqrt(dx * dx + dy * dy) || 1, ex = dx / ln * 14, ey = dy / ln * 14;
  var NS = "http://www.w3.org/2000/svg", s = document.createElementNS(NS, "svg"), l = document.createElementNS(NS, "line");
  s.setAttribute("class", "wl"); s.style.color = b[wl[0]] === "X" ? "var(--x)" : "var(--o)";
  l.setAttribute("x1", ax - ex); l.setAttribute("y1", ay - ey); l.setAttribute("x2", zx + ex); l.setAttribute("y2", zy + ey);
  l.setAttribute("stroke", "currentColor");
  s.appendChild(l); g.appendChild(s);
  var tl = ln + 28;
  anim(l, [{strokeDasharray: tl + "px", strokeDashoffset: tl + "px"}, {strokeDasharray: tl + "px", strokeDashoffset: "0px"}], {duration: 450, delay: 200, easing: "ease-out", fill: "backwards"});
}
function paint(msg, cls, canPlay) {
  for (var i = 0; i < 9; i++) {
    var c = cells[i], v = b[i];
    c.className = "c" + (v === "X" ? " x" : v === "O" ? " o" : "") + (wl.indexOf(i) >= 0 ? " w" : "");
    c.disabled = !canPlay || !!v;
    if (shown[i] !== v) {
      c.innerHTML = v ? markSVG(v) : "";
      if (v && !shown[i]) {   // tanda baru: digambar bertahap + membal
        var ps = c.querySelectorAll("path,circle");
        for (var k = 0; k < ps.length; k++) anim(ps[k], [{strokeDasharray: "1", strokeDashoffset: 1}, {strokeDasharray: "1", strokeDashoffset: 0}], {duration: 240, delay: k * 130, easing: "ease-out", fill: "backwards"});
        anim(c.firstChild, [{transform: "scale(.6)", opacity: .2}, {transform: "scale(1)", opacity: 1}], {duration: 260, easing: "cubic-bezier(.2,1.6,.4,1)"});
      }
      shown[i] = v;
    }
  }
  drawLine();
  $("sx").textContent = sc.x; $("so").textContent = sc.o; $("sd").textContent = sc.d;
  st.className = "st" + (cls ? " " + cls : ""); st.textContent = msg;
}
// ---- lawan bot
function renderBot(res) {
  wl = res ? res.l : [];
  var m = "Giliran kamu", cls = "";
  if (over) {
    if (res.w === "X") { m = "Kamu menang! 🎉"; cls = "win"; }
    else if (res.w === "O") { m = "Bot menang 🤖"; cls = "lose"; }
    else m = "Seri 🤝";
  } else if (busy) m = "Bot berpikir...";
  paint(m, cls, !over && !busy);
}
var nextT = null;
function finish(r) {
  over = true; bsc[r.w === "X" ? "x" : r.w === "O" ? "o" : "d"]++; sc = bsc; save(); renderBot(r);
  playAnim(r.w === "X" ? "win" : r.w === "O" ? "lose" : "draw");
  clearTimeout(nextT); nextT = setTimeout(function () { if (mode === "bot" && over) botRound(); }, ANIM_MS);   // setelah animasi, lanjut ronde berikutnya
}
function botPlay(i) {
  if (over || busy || b[i]) return;
  hap(); b[i] = "X";
  var r = win(b);
  if (r) return finish(r);
  busy = true; renderBot();
  setTimeout(function () {
    b[botMove()] = "O"; busy = false;
    var r2 = win(b);
    if (r2) finish(r2); else renderBot();
  }, 150);
}
function botRound() { clearTimeout(nextT); stopAnim(); b = ["", "", "", "", "", "", "", "", ""]; over = false; busy = false; renderBot(); }
function sides(l, r) { $("pl1").style.setProperty("--ac", l); $("pl2").style.setProperty("--ac", r); }
function showDiff() {
  for (var k = 1; k <= 4; k++) { var r = bscs[k]; $("rc" + k).textContent = (r.x + r.o + r.d) ? "Rekor kamu: " + r.x + " menang \u00b7 " + r.d + " seri \u00b7 " + r.o + " kalah" : "Belum pernah dimainkan"; }
  show("df");
}
function startBot(lv) {
  LV = lv || LV; bsc = bscs[LV];
  stopPoll(); mode = "bot"; net = null; sc = bsc; sides("var(--x)", "var(--o)");
  $("mode").textContent = "Lawan Bot \u00b7 " + NAMES[LV]; $("vs").textContent = ""; $("l1").textContent = "Kamu"; $("l2").textContent = "Bot";
  show("gm"); botRound();
}
// ---- lawan teman
function api(path, body) {
  var o = {headers: {"X-Init-Data": INIT}};
  if (body) { o.method = "POST"; o.headers["Content-Type"] = "application/json"; o.body = JSON.stringify(body); }
  return fetch(path, o).then(function (r) { return r.json().then(function (j) { j.__ok = r.ok; return j; }); });
}
function stopPoll() { if (timer) { clearInterval(timer); timer = null; } }
function renderNet() {
  if (!net) return;
  var N = (hold && Date.now() < hold.until) ? hold.net : net;
  b = N.b; wl = N.line || []; over = N.over;
  var me = N.me;
  sc = me === "X" ? N.score : {x: N.score.o, o: N.score.x, d: N.score.d};
  // skor selalu ditampilkan: sisi kiri = kamu, kanan = lawan; warna mengikuti tanda masing-masing
  var mine = me === "X" ? N.score.x : N.score.o, theirs = me === "X" ? N.score.o : N.score.x;
  sides(me === "X" ? "var(--x)" : "var(--o)", me === "X" ? "var(--o)" : "var(--x)");
  $("l1").textContent = "Kamu"; $("l2").textContent = N.opp;
  $("vs").textContent = "Kamu (" + me + ") lawan " + N.opp + " (" + (me === "X" ? "O" : "X") + ")";
  var m, cls = "", can = false;
  if (!N.joined) m = "Menunggu " + N.opp + " bergabung...";
  else if (over) {
    if (N.res === "D") m = "Seri 🤝";
    else if (N.res === me) { m = "Kamu menang! 🎉"; cls = "win"; }
    else { m = N.opp + " menang"; cls = "lose"; }
  } else if (N.turn === me) { m = "Giliran kamu"; can = true; }
  else m = "Giliran " + N.opp;
  paint(m, cls, can);
  $("sx").textContent = mine; $("so").textContent = theirs; $("sd").textContent = N.score.d;
}
function gotNet(j) {
  if (!j || j.__ok === false) {
    stopPoll();
    st.className = "st lose"; st.textContent = (j && j.error) || "Terhubung gagal, coba lagi.";
    for (var i = 0; i < 9; i++) cells[i].disabled = true;
    return;
  }
  net = j; gid = j.id;
  if (j.joined) {
    if (j.over && j.rid !== animRid) {   // ronde baru selesai: tahan papan akhir sambil memutar animasi, setelah itu lanjut ronde
      animRid = j.rid; hold = {net: j, until: Date.now() + ANIM_MS};
      renderNet();   // papan akhir + garis pemenang tampil dulu, baru animasi (sel pemenang sudah dikenal)
      playAnim(j.res === "D" ? "draw" : j.res === j.me ? "win" : "lose");
      setTimeout(function () { hold = null; renderNet(); }, ANIM_MS + 40);
      return;
    } else if (!j.over && j.last && j.last.rid !== animRid) {   // ronde sudah selesai sebelum sempat terlihat: animasinya tetap diputar
      animRid = j.last.rid;
      playAnim(j.last.res === "D" ? "draw" : j.last.res === j.me ? "win" : "lose");
    }
  }
  renderNet();
}
function poll() { if (mode === "net" && gid) api("api/tttstate?g=" + gid).then(gotNet, function () {}); }
function resetBoardView() { shown = ["", "", "", "", "", "", "", "", ""]; lineKey = ""; for (var i = 0; i < 9; i++) cells[i].innerHTML = ""; var o = g.querySelector(".wl"); if (o) g.removeChild(o); }
function openNet(id) {
  stopPoll(); animRid = -1; hold = null; stopAnim(); mode = "net"; gid = id; net = null; b = ["", "", "", "", "", "", "", "", ""]; over = false; wl = [];
  resetBoardView();
  $("mode").textContent = "Lawan Teman"; $("vs").textContent = ""; show("gm");
  paint("Memuat...", "", false);
  api("api/tttstate?g=" + id).then(gotNet, function () { paint("Gagal terhubung.", "lose", false); });
  timer = setInterval(poll, 1500);
}
function friends() {
  stopPoll(); mode = "menu"; show("fr");
  var fl = $("fl"); fl.innerHTML = "<div class='sec'>Memuat...</div>";
  api("api/tttplayers").then(function (j) {
    if (j.__ok === false) { fl.innerHTML = ""; var d = document.createElement("div"); d.className = "sec"; d.textContent = j.error || "Gagal memuat."; fl.appendChild(d); return; }
    fl.innerHTML = "";
    function head(t) { var d = document.createElement("div"); d.className = "sec"; d.textContent = t; fl.appendChild(d); }
    function row(name, extra, label, fn) {
      var r = document.createElement("div"); r.className = "row";
      var av = document.createElement("div"); av.className = "av"; av.textContent = (name || "?").charAt(0).toUpperCase(); r.appendChild(av);
      var s = document.createElement("span"); s.textContent = name; r.appendChild(s);
      if (extra) { var e = document.createElement("i"); e.textContent = extra; r.appendChild(e); }
      var bt = document.createElement("button"); bt.textContent = label; bt.addEventListener("click", fn); r.appendChild(bt);
      fl.appendChild(r);
    }
    if (j.games.length) {
      head("PERMAINAN BERJALAN");
      j.games.forEach(function (x) { row(x.opp, !x.joined ? "menunggu" : x.mine ? "giliranmu" : "", "Lanjut", function () { openNet(x.id); }); });
    }
    head("TEMAN TERDAFTAR");
    if (!j.players.length) head("Belum ada teman lain yang terdaftar di bot.");
    j.players.forEach(function (p) {
      row(p.name, "", "Undang", function () {
        api("api/tttinvite", {to: p.id}).then(function (r) {
          if (r.__ok === false) { alert(r.error || "Gagal mengundang."); return; }
          openNet(r.id);
        });
      });
    });
  }, function () { fl.textContent = "Gagal memuat daftar teman."; });
}
function play(i) {
  if (mode === "bot") return botPlay(i);
  if (mode === "net" && net && net.joined && !net.over && net.turn === net.me && !net.b[i]) {
    hap(); net.b[i] = net.me; net.turn = net.me === "X" ? "O" : "X"; renderNet();
    api("api/tttmove", {g: gid, c: i}).then(gotNet, function () {});
  }
}
$("mb").addEventListener("click", showDiff);
$("db").addEventListener("click", function () { show("menu"); });
var dfb = document.querySelectorAll("#df .big");
for (var z = 0; z < dfb.length; z++) dfb[z].addEventListener("click", function () { hap(); startBot(+this.getAttribute("data-lv")); });
$("mf").addEventListener("click", friends);
$("fb").addEventListener("click", function () { show("menu"); });
$("gb").addEventListener("click", function () { stopPoll(); stopAnim(); clearTimeout(nextT); hold = null; mode = "menu"; show("menu"); });
$("rr").addEventListener("click", function () {
  if (mode === "bot") botRound(); else if (mode === "net") api("api/tttround", {g: gid}).then(gotNet, function () {});
});
$("rs").addEventListener("click", function () {
  if (mode === "bot") { bscs[LV] = blank(); bsc = bscs[LV]; sc = bsc; save(); botRound(); }
  else if (mode === "net") api("api/tttreset", {g: gid}).then(gotNet, function () {});
});
var q = /[?&]g=([0-9a-f]{8})/.exec(location.search);
if (q) openNet(q[1]); else show("menu");
})();
</script>
</body></html>
"""


# ---------------------------------------------------------------- server
class H(BaseHTTPRequestHandler):
    server_version = "LaguApp/1"

    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        b = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(b)

    def _json(self, code, obj):
        self._send(code, json.dumps(obj, ensure_ascii=False))

    def _user(self):
        u = check_init(self.headers.get("X-Init-Data", ""))
        return u if u and allowed(u["id"]) else None

    def _stream(self, qs, video=False):
        vid = (qs.get("v") or [""])[0]
        sig = (qs.get("s") or [""])[0]
        try:
            exp = int((qs.get("e") or ["0"])[0])
        except ValueError:
            exp = 0
        if not VID_RE.match(vid) or (exp and exp < time.time()) or not hmac.compare_digest(sig, sign(vid, exp)):
            return self._json(403, {"error": "Tautan audio tidak sah."})
        if video:
            f = vcached_file(vid)
            if not f:
                return self._json(404, {"error": "Video belum siap."})
            try:
                os.utime(f)
            except OSError:
                pass
        else:
            f = cached_file(vid)
        if not f:
            try:   # file sudah terhapus dari cache (kena batas jumlah) -> unduh ulang otomatis, jadi tautan lama tetap bisa dipakai
                f = yt_fetch(vid)
            except Exception as e:
                sys.stderr.write("[stream] unduh ulang gagal: %s\n" % e)
                return self._json(404, {"error": "Audio belum siap."})
        size = os.path.getsize(f)
        start, end, code = 0, size - 1, 200
        m = re.match(r"bytes=(\d*)-(\d*)$", self.headers.get("Range", "").strip())
        if m and (m.group(1) or m.group(2)):
            if m.group(1):
                start = int(m.group(1))
                end = int(m.group(2)) if m.group(2) else size - 1
            else:
                start = max(0, size - int(m.group(2)))
            end = min(end, size - 1)
            if start > end or start >= size:
                self.send_response(416)
                self.send_header("Content-Range", "bytes */%d" % size)
                self.end_headers()
                return
            code = 206
        self.send_response(code)
        self.send_header("Content-Type", (VMIME if video else MIME).get(os.path.splitext(f)[1].lower(), "application/octet-stream"))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(end - start + 1))
        if code == 206:
            self.send_header("Content-Range", "bytes %d-%d/%d" % (start, end, size))
        self.send_header("Cache-Control", "private, max-age=3600")
        self.end_headers()
        try:
            with open(f, "rb") as fh:
                fh.seek(start)
                left = end - start + 1
                while left > 0:
                    b = fh.read(min(65536, left))
                    if not b:
                        break
                    self.wfile.write(b)
                    left -= len(b)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _pl(self, kind, body):
        u = self._user()
        if not u:
            return self._json(403, {"error": "Akses ditolak. Buka lewat tombol di bot."})
        try:
            res = pl_api(kind, str(u["id"]), body)
            if kind == "add" and res.get("ok"):
                try:
                    ms = max(0, int(body.get("ms") or 0))
                except (TypeError, ValueError):
                    ms = 0
                warm_async(body.get("title", ""), body.get("artist", ""), ms)
            elif kind == "get":
                for it in (res.get("items") or [])[:3]:
                    warm_async(it.get("title", ""), it.get("artist", ""), it.get("ms", 0))
            return self._json(200, res)
        except Exception as e:
            sys.stderr.write("[playlist] %s gagal: %s\n" % (kind, e))
            return self._json(400, {"error": "Playlist gagal diproses (%s)" % str(e)[:60]})

    def _ttt(self, kind, body):
        u = self._user()
        if not u:
            return self._json(403, {"error": "Akses ditolak. Buka lewat tombol di bot."})
        try:
            code, obj = ttt_api(kind, u, body)
        except Exception as e:
            sys.stderr.write("[ttt] %s gagal: %s\n" % (kind, e))
            code, obj = 500, {"error": "Terjadi kesalahan di server game."}
        return self._json(code, obj)

    def do_GET(self):
        pu = urllib.parse.urlparse(self.path)
        p = pu.path.rstrip("/")
        m = re.search(r"/api/ttt(players|state)$", p)
        if m:
            return self._ttt(m.group(1), {"g": (urllib.parse.parse_qs(pu.query).get("g") or [""])[0][:16]})
        if p.endswith("/ttt"):
            return self._send(200, TTT_HTML, "text/html; charset=utf-8")
        if p.endswith("/api/search"):
            u = self._user()
            if not u:
                return self._json(403, {"error": "Akses ditolak. Buka lewat tombol di bot."})
            q = (urllib.parse.parse_qs(pu.query).get("q") or [""])[0].strip()[:100]
            if not q:
                return self._json(200, {"items": []})
            try:
                return self._json(200, {"items": search(q)})
            except Exception as e:
                sys.stderr.write("[search] gagal: %s\n" % e)
                return self._json(502, {"error": "Pencarian gagal, coba lagi sebentar lagi."})
        if p.endswith("/api/stream"):
            return self._stream(urllib.parse.parse_qs(pu.query))
        if p.endswith("/api/vstream"):
            return self._stream(urllib.parse.parse_qs(pu.query), True)
        if p.endswith("/api/vinfo"):
            if not self._user():
                return self._json(403, {"error": "Akses ditolak. Buka lewat tombol di bot."})
            if not VIDEO_ON:
                return self._json(200, {"off": True})
            vid = (urllib.parse.parse_qs(pu.query).get("v") or [""])[0]
            if not VID_RE.match(vid):
                return self._json(200, {"off": True})
            f = vcached_file(vid)
            if f:
                return self._json(200, {"ready": True, "url": "api/vstream?v=%s&e=0&s=%s" % (vid, sign(vid, 0))})
            if time.time() - _vfail.get(vid, 0) < 600:
                return self._json(200, {"off": True})   # sudah pernah gagal, jangan dicoba terus
            video_async(vid)
            return self._json(200, {"ready": False})
        if p.endswith("/api/phase"):
            if not self._user():
                return self._json(403, {"error": "Akses ditolak. Buka lewat tombol di bot."})
            qs = urllib.parse.parse_qs(pu.query)
            return self._json(200, {"p": _phase.get(res_key((qs.get("title") or [""])[0][:200], (qs.get("artist") or [""])[0][:200]), "")})
        if p.endswith("/api/resolve"):
            u = self._user()
            if not u:
                return self._json(403, {"error": "Akses ditolak. Buka lewat tombol di bot."})
            qs = urllib.parse.parse_qs(pu.query)
            hit = resolve_fast((qs.get("title") or [""])[0][:200], (qs.get("artist") or [""])[0][:200])
            if hit:   # sudah ada di cache: langsung dijawab, tanpa batas laju dan tanpa menunggu lagu lain
                return self._json(200, hit)
            bg = (qs.get("bg") or [""])[0] == "1"   # permintaan prefetch punya jatah laju sendiri, jadi tidak menghambat lagu yang sedang diketuk
            uid, now = str(u["id"]) + (":bg" if bg else ""), time.time()
            with LOCK:
                if now - _last_res.get(uid, 0) < 2:
                    return self._json(429, {"error": "Pelan-pelan, tunggu sebentar."})
                _last_res[uid] = now
            try:
                ms = int((qs.get("ms") or ["0"])[0] or 0)
            except ValueError:
                ms = 0
            try:
                return self._json(200, resolve((qs.get("title") or [""])[0][:200], (qs.get("artist") or [""])[0][:200], ms))
            except Exception as e:
                sys.stderr.write("[resolve] gagal: %s\n" % e)
                return self._json(502, {"error": str(e)[:120] or "Gagal menyiapkan lagu."})
        if p.endswith("/api/lyrics"):
            if not self._user():
                return self._json(403, {"error": "Akses ditolak. Buka lewat tombol di bot."})
            qs = urllib.parse.parse_qs(pu.query)
            try:
                ms = int((qs.get("ms") or ["0"])[0] or 0)
            except ValueError:
                ms = 0
            return self._json(200, get_lyrics(clean((qs.get("title") or [""])[0], 120), clean((qs.get("artist") or [""])[0], 80), ms))
        if p.endswith("/api/preview"):
            if not self._user():
                return self._json(403, {"error": "Akses ditolak. Buka lewat tombol di bot."})
            qs = urllib.parse.parse_qs(pu.query)
            return self._json(200, {"url": find_preview((qs.get("title") or [""])[0], (qs.get("artist") or [""])[0])})
        if p.endswith("/api/pl"):
            return self._pl("get", {})
        if p.endswith("/api/recent"):
            if not self._user():
                return self._json(403, {"error": "Akses ditolak. Buka lewat tombol di bot."})
            return self._json(200, {"items": recent_uniq(recent_load())})
        self._send(200, HTML, "text/html; charset=utf-8")

    def do_POST(self):
        p = urllib.parse.urlparse(self.path).path.rstrip("/")
        m = re.search(r"/api/ttt(invite|move|round|reset)$", p)
        if m:
            try:
                n = int(self.headers.get("Content-Length", "0"))
                d = json.loads(self.rfile.read(min(n, 1024)) or b"{}")
                if not isinstance(d, dict):
                    d = {}
            except Exception:
                return self._json(400, {"error": "Permintaan tidak valid."})
            return self._ttt(m.group(1), d)
        m = re.search(r"/api/pl(add|del|clear)$", p)
        if m:
            try:
                n = int(self.headers.get("Content-Length", "0"))
                d = json.loads(self.rfile.read(min(n, 4096)) or b"{}")
                if not isinstance(d, dict):
                    d = {}
            except Exception:
                return self._json(400, {"error": "Permintaan tidak valid."})
            return self._pl(m.group(1), d)
        if not p.endswith("/api/play"):
            return self._json(404, {"error": "tidak ada"})
        u = self._user()
        if not u:
            return self._json(403, {"error": "Akses ditolak. Buka lewat tombol di bot."})
        uid = str(u["id"])
        now = time.time()
        with LOCK:
            if now - _last_play.get(uid, 0) < 3:
                return self._json(429, {"error": "Pelan-pelan, tunggu 3 detik."})
            _last_play[uid] = now
        try:
            n = int(self.headers.get("Content-Length", "0"))
            d = json.loads(self.rfile.read(min(n, 4096)) or b"{}")
            enqueue_play(u, d.get("title", ""), d.get("artist", ""), d.get("cover", ""))
        except Exception as e:
            return self._json(400, {"error": "Permintaan tidak valid (%s)" % e})
        return self._json(200, {"ok": True})


HTML = r"""<!doctype html>
<html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>Spotify</title>
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
<style>
:root{--g:#1db954;--bg:#171717;--card2:#242424;--tx:#fff;--mu:#a7a7a7}
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
html,body{margin:0;background:var(--bg);color:var(--tx);font-family:"Circular Std","Segoe UI",Roboto,system-ui,-apple-system,sans-serif}
body{padding:14px;padding-bottom:calc(14px + env(safe-area-inset-bottom,0px))}
.card{max-width:480px;margin:0 auto;border-radius:26px;padding:18px 16px 14px;background:linear-gradient(180deg,#2e2e2e 0%,#1e1e1e 30%,#141414 68%,#121212 100%);box-shadow:0 0 0 1px #2c2c2c inset,0 12px 32px rgba(0,0,0,.4)}
.head{display:flex;align-items:center;justify-content:space-between}
.brand{display:flex;align-items:center;gap:10px}
.logo{width:40px;height:40px;flex:none}
.name{font-size:27px;font-weight:800;letter-spacing:-.6px;line-height:1}
.rg{font-size:10px;font-weight:600;vertical-align:top;margin-left:1px;color:#cfcfcf;letter-spacing:0}
.sub{color:var(--mu);font-size:13px;margin-top:5px}
.live{border:1.5px solid var(--g);color:var(--g);border-radius:999px;padding:5px 14px;font-size:12px;font-weight:700;letter-spacing:2px}
.tabs{display:flex;gap:8px;margin:18px 0 12px}
.tab{flex:1;border:0;border-radius:999px;padding:14px 4px;font-size:14px;font-weight:600;background:var(--card2);color:var(--tx)}
.tab.on{background:var(--g);color:#000;font-weight:700}
.stat{display:flex;align-items:center;gap:8px;color:#b3b3b3;font-size:14px;margin:6px 2px 12px;min-height:20px}
.dot{width:9px;height:9px;border-radius:50%;background:var(--g);flex:none}
.sbox{display:flex;align-items:center;gap:10px;background:#232323;border-radius:18px;padding:0 14px;height:50px;margin-bottom:10px}
.sbox input{flex:1;background:none;border:0;outline:0;color:var(--tx);font-size:16px;min-width:0}
.sbox input::placeholder{color:#808080}
.list{min-height:120px}
.it{display:flex;align-items:center;gap:12px;padding:8px 4px;border-radius:10px;cursor:pointer}
.it:active{background:#242424}
.cv{width:66px;height:66px;border-radius:6px;background:#2a2a2a;object-fit:cover;flex:none}
.tx{min-width:0;flex:1}
.t{font-size:16.5px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.a{font-size:14px;color:var(--mu);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-top:3px}
.empty{color:var(--mu);text-align:center;padding:34px 8px;font-size:14px}
.pager{display:flex;align-items:center;justify-content:center;gap:12px;margin-top:8px}
.pager button{width:44px;height:34px;border:0;border-radius:10px;background:#2a2a2a;color:#b3b3b3;font-size:16px}
.pager button:disabled{opacity:.35}
.pager span{color:var(--mu);font-size:14px;min-width:34px;text-align:center}
.player{display:flex;align-items:center;gap:12px;background:#242424;border-radius:16px;padding:10px 12px;margin-top:12px;position:-webkit-sticky;position:sticky;bottom:calc(8px + env(safe-area-inset-bottom,0px));z-index:30;box-shadow:0 0 0 1px #333 inset,0 -10px 24px rgba(18,18,18,.95),0 8px 20px rgba(0,0,0,.5)}
.player .cv{width:48px;height:48px}
.pbtn{width:44px;height:44px;border-radius:50%;border:0;background:var(--g);color:#000;font-size:20px;flex:none;display:flex;align-items:center;justify-content:center;padding:0;transition:transform .12s}
.pbtn:active,.npb:active{transform:scale(.92)}
.pbtn svg,.npb svg{width:1em;height:1em;fill:currentColor;display:block}
.npb svg.lp{fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
.bar{height:4px;background:#3a3a3a;border-radius:2px;margin-top:8px;overflow:hidden}
.bar i{display:block;height:100%;width:0;background:var(--g)}
.it.on .t{color:var(--g)}
.barw{padding:8px 0 4px;cursor:pointer}
.barw .bar{margin-top:0}
.addb{width:36px;height:36px;border-radius:50%;border:1.5px solid #4a4a4a;background:none;color:#fff;font-size:20px;line-height:1;flex:none;padding:0}
.addb.done{border-color:var(--g);color:var(--g)}
.addb:disabled{opacity:.5}
.pbtn.sm{width:38px;height:38px;font-size:18px;background:none;color:#fff}
.pctl{display:flex;gap:8px;margin:4px 0 10px;flex-wrap:wrap}
.pctl button{flex:1;min-width:44%;border:0;border-radius:999px;padding:11px 6px;font-size:13.5px;font-weight:600;background:var(--card2);color:var(--tx)}
.pctl button.g{background:var(--g);color:#000}
.pctl button.on{outline:2px solid var(--g)}
.player{cursor:pointer}
.np{position:fixed;left:0;top:0;right:0;bottom:0;z-index:50;background:#121212;color:#fff;overflow-y:auto;-webkit-overflow-scrolling:touch;--acc:rgb(90,31,58);transform:translateY(0);opacity:1;transition:transform .34s cubic-bezier(.22,1,.36,1),opacity .25s ease-out}
.np.closed{transform:translateY(100%);opacity:0;visibility:hidden;pointer-events:none;transition:transform .28s cubic-bezier(.4,0,1,1),opacity .28s ease-in,visibility 0s linear .28s}
@keyframes tin{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
#p-cari,#p-global,#p-pl{animation:tin .24s ease-out}
.it{animation:tin .22s ease-out backwards;transition:background .15s,transform .12s}
.it:active{transform:scale(.985)}
.tab{transition:background .2s,color .2s,transform .12s}
.tab:active{transform:scale(.96)}
.player{animation:tin .26s ease-out}
.npin{max-width:480px;margin:0 auto;padding-bottom:calc(28px + env(safe-area-inset-bottom,0px))}
.nphero{position:relative;height:min(112vw,520px);background:#222 center/cover no-repeat}
.nphero:after{content:"";position:absolute;left:0;right:0;top:0;bottom:0;background:linear-gradient(180deg,rgba(0,0,0,.5) 0%,rgba(0,0,0,0) 28%,rgba(0,0,0,0) 48%,#121212 100%)}
.nptop{position:absolute;left:0;right:0;top:0;z-index:2;display:flex;align-items:center;justify-content:space-between;padding:calc(10px + env(safe-area-inset-top,0px)) 12px 10px;font-weight:700;font-size:15px}
.npb{width:40px;height:40px;border:0;border-radius:50%;background:rgba(0,0,0,.3);color:#fff;display:flex;align-items:center;justify-content:center;padding:0;font-size:17px;flex:none}
.npb.on{color:var(--g)}
.npb:disabled{opacity:.3}
.npmeta{position:absolute;left:0;right:0;bottom:0;z-index:2;display:flex;align-items:flex-end;gap:10px;padding:0 18px 14px}
.npmeta .nm{flex:1;min-width:0}
.npt{font-size:30px;font-weight:800;line-height:1.1;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;text-shadow:0 2px 12px rgba(0,0,0,.5)}
.npa{font-size:15px;color:#e0e0e0;margin-top:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.npprog{margin:4px 18px 0}
.np .bar{height:5px}
.nptm{display:flex;justify-content:space-between;font-size:12px;color:#b3b3b3;margin-top:2px}
.npctl{display:flex;align-items:center;justify-content:center;gap:22px;margin:12px 18px 4px}
.npctl .npb{background:none;width:50px;height:50px;font-size:28px}
.npctl .npplay{width:68px;height:68px;background:#fff;color:#000;font-size:34px}
.npctl .npb.on{color:var(--g)}
.npcard{margin:14px 14px 0;border-radius:14px;padding:16px;background:var(--acc)}
.npcard h4{margin:0 0 10px;font-size:15px;font-weight:700}
.nplines{position:relative;overflow:hidden;contain:layout paint;transition:height .6s cubic-bezier(.22,1,.36,1);scroll-behavior:auto}
.nli{position:relative;transition:transform .6s cubic-bezier(.22,1,.36,1)}
.open .nplines{max-height:52vh;overflow-y:auto}
.ll{font-size:22px;font-weight:800;line-height:1.25;color:rgba(255,255,255,.5);margin:6px 0;transform-origin:left center;transition:color .5s ease,opacity .5s ease,transform .6s cubic-bezier(.22,1,.36,1),filter .5s ease}
.ll.cur{color:#fff}
.npcard:not(.open) .ll.past,.npcard:not(.open) .ll.far{opacity:0}
.npart{background:#1c1c1c}
.arow{display:flex;align-items:center;gap:12px}
.arow img{width:56px;height:56px;border-radius:50%;object-fit:cover;background:#2a2a2a;flex:none}
.arow b{flex:1;min-width:0;font-size:17px}
.arow button{border:1px solid #6a6a6a;background:none;color:#fff;border-radius:999px;padding:8px 14px;font-size:13px;font-weight:700;flex:none}
.hide{display:none!important}

/* ===== tampilan ala Spotify ===== */
:root{--g:#1ed760;--bg:#121212;--card2:#2a2a2a;--mu:#b3b3b3}
html,body{background:#121212}
.card{background:linear-gradient(180deg,#2b2b2b 0%,#1c1c1c 28%,#141414 62%,#121212 100%)}
.si{fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
.sf{fill:currentColor}
.tab{background:#2a2a2a;font-weight:700}
.tab.on{background:#1ed760;color:#000}
.pctl button{display:flex;align-items:center;justify-content:center;gap:8px;background:#2a2a2a;font-weight:700}
.pctl button svg{width:18px;height:18px;flex:none;display:block}
.pctl button.g{background:#1ed760;color:#000}
.pctl button.on{outline:0;color:#1ed760;box-shadow:0 0 0 2px #1ed760 inset}
.pctl button:active{transform:scale(.97)}
.pager button{display:flex;align-items:center;justify-content:center;padding:0}
.pager button svg{width:20px;height:20px;display:block}
.it{animation:none!important;border-radius:8px;padding:8px 6px}
.it:hover{background:#2a2a2a}
.it:active{background:#333}
.cv{border-radius:4px}
.t{font-weight:700}
.a{color:#b3b3b3}
.addb{display:flex;align-items:center;justify-content:center;border:0;background:none;color:#b3b3b3;width:40px;height:40px;padding:0}
.addb svg{width:24px;height:24px;display:block}
.addb.done{color:#1ed760;border:0}
.addb:active{transform:scale(.9)}
.pbtn{background:#fff;color:#000}
.pbtn.sm{background:none;color:#fff}
.bar{background:#4d4d4d}
.bar i{background:#fff}
.player{background:#2a2a2a}
.live{border-color:#1ed760;color:#1ed760}
.dot{background:#1ed760}
.nphero{overflow:hidden}
.npbg{position:absolute;left:-12%;top:-12%;width:124%;height:124%;background:#222;opacity:0;transition:opacity .6s ease;pointer-events:none}
.nphero.hv .npbg{opacity:1}
.npvid{position:absolute;left:0;top:0;width:100%;height:100%;opacity:0;transition:opacity .6s ease;pointer-events:none;background:transparent}
.vhid{position:fixed;right:0;bottom:0;width:2px;height:2px;opacity:.02;pointer-events:none;z-index:-1}
.npvid.on{opacity:1}
.npb svg.lp,.pctl svg.lp{fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}

/* ===== Beranda ala Spotify ===== */
body{padding-bottom:calc(150px + env(safe-area-inset-bottom,0px))}
.tabs{display:none}
.home,.card{max-width:480px;margin:0 auto}
.htop{display:flex;align-items:center;gap:8px;padding:2px 0 14px;overflow-x:auto;scrollbar-width:none}
.htop::-webkit-scrollbar,.hscroll::-webkit-scrollbar{display:none}
.hav{width:36px;height:36px;border-radius:50%;flex:none;margin-right:6px;overflow:hidden;display:flex;align-items:center;justify-content:center;font-weight:800;font-size:16px;color:#fff;background:linear-gradient(135deg,#7b4bff,#e0457b)}
.hav img{width:100%;height:100%;object-fit:cover;display:block}
.chip{flex:none;border:0;border-radius:999px;height:34px;padding:0 16px;font-size:14px;font-weight:600;background:#2a2a2a;color:#fff;font-family:inherit}
.chip.on{background:#1ed760;color:#000}
.hgrid{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.ht{display:flex;align-items:center;gap:10px;height:56px;border-radius:6px;background:#2a2a2a;overflow:hidden;cursor:pointer}
.ht:active{background:#333}
.ht .hcv,.ht .hart{width:56px;height:56px;flex:none;object-fit:cover;background:#3a3a3a;border-radius:0}
.ht span{font-size:13.5px;font-weight:700;line-height:1.2;padding-right:8px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;word-break:break-word}
.hart{display:flex;align-items:center;justify-content:center;color:#fff}
.hart svg{width:26px;height:26px;display:block}
.hart.g1{background:linear-gradient(135deg,#4a2bff,#8fb7ff)}
.hart.g2{background:linear-gradient(135deg,#0c8f5a,#1ed760)}
.hart.g2 svg{fill:none;stroke:#fff;stroke-width:1.9;stroke-linecap:round}
.hh{font-size:21px;font-weight:800;letter-spacing:-.4px;margin:30px 0 14px}
.hscroll{display:flex;gap:14px;overflow-x:auto;scrollbar-width:none;margin:0 -14px;padding:0 14px 4px;-webkit-overflow-scrolling:touch}
.hc{flex:none;width:158px;cursor:pointer}
.hc .hcc{width:158px;height:158px;border-radius:4px;object-fit:cover;background:#2a2a2a;display:block}
.hc .hs{font-size:13px;color:#b3b3b3;margin-top:8px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.hc .hn{font-size:14px;font-weight:700;margin-top:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.hc .hn+.hs{margin-top:2px}
.hr{display:flex;align-items:center;gap:12px;padding:7px 0;cursor:pointer}
.hr:active{opacity:.7}
.hr .hrc{width:52px;height:52px;border-radius:4px;object-fit:cover;background:#2a2a2a;flex:none}
.hr .tx{min-width:0;flex:1}
.hrt{font-size:16px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.hr .a{font-size:14px;margin-top:2px}
.hmore{border:0;background:none;color:#fff;width:36px;height:40px;padding:0;display:flex;align-items:center;justify-content:center;flex:none}
.hmore svg{width:22px;height:22px;display:block}
.bnav{position:fixed;left:0;right:0;bottom:0;z-index:40;padding-bottom:env(safe-area-inset-bottom,0px);background:linear-gradient(180deg,rgba(0,0,0,0) 0%,rgba(0,0,0,.9) 34%,#000 100%)}
.bin{display:flex;max-width:480px;margin:0 auto}
.bin button{flex:1;border:0;background:none;color:#b3b3b3;display:flex;flex-direction:column;align-items:center;gap:4px;padding:12px 0 9px;font-size:11px;font-weight:600;font-family:inherit}
.bin button.on{color:#fff}
.bin svg{width:26px;height:26px;display:block;fill:none;stroke:currentColor;stroke-width:1.9;stroke-linejoin:round;stroke-linecap:round}
.bin .on svg .f{fill:currentColor}
.bin .on svg{stroke-width:2.4}
.player{position:fixed;left:8px;right:8px;bottom:calc(68px + env(safe-area-inset-bottom,0px));max-width:464px;margin:0 auto;z-index:45}
.player{box-shadow:0 0 0 1px rgba(255,255,255,.07) inset,0 3px 10px rgba(0,0,0,.35);animation:none}   /* bayangan blur besar dihapus: di sebagian WebView Android tergambar sebagai kotak hitam menutupi menu bawah */
.toast{position:fixed;left:50%;transform:translateX(-50%);bottom:calc(150px + env(safe-area-inset-bottom,0px));z-index:60;max-width:88%;background:#fff;color:#000;font-size:14px;font-weight:600;padding:10px 16px;border-radius:8px;box-shadow:0 6px 20px rgba(0,0,0,.5);text-align:center}
@media(min-width:900px){.home,.card,.npin,.bin{max-width:760px}.player{max-width:744px}}

/* ===== Layout desktop (laptop / PC) ala Spotify ===== */
.dtop,.dside,.dbar{display:none}
.hhead{display:flex;align-items:baseline;justify-content:space-between}
.hall{display:none}
.dsk{display:none}
@media(min-width:1000px){
html,body{height:100%;overflow:hidden;background:#000}
body{padding:0!important}
.bnav,.player{display:none!important}
.dtop{display:flex;position:fixed;left:0;right:0;top:0;height:64px;padding:0 150px;align-items:center;justify-content:center;gap:10px;z-index:20}
.dhome{width:48px;height:48px;border-radius:50%;border:0;background:#1f1f1f;color:#b3b3b3;display:flex;align-items:center;justify-content:center;padding:0;flex:none}
.dhome:hover,.dhome.on{color:#fff}
.dhome svg{width:26px;height:26px;fill:none;stroke:currentColor;stroke-width:2;stroke-linejoin:round}
.dhome.on svg path{fill:currentColor}
.dsearch{display:flex;align-items:center;gap:10px;width:min(100%,470px);height:48px;border-radius:999px;background:#1f1f1f;padding:0 16px;border:2px solid transparent;color:#b3b3b3}
.dsearch:hover{background:#2a2a2a}
.dsearch:focus-within{border-color:#fff;color:#fff}
.dsearch svg{width:22px;height:22px;flex:none;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round}
.dsearch input{flex:1;min-width:0;background:none;border:0;outline:0;color:#fff;font-size:15px;font-family:inherit}
.dav{position:absolute;right:150px;top:14px;width:38px;height:38px;border-radius:50%;overflow:hidden;display:flex;align-items:center;justify-content:center;font-weight:800;color:#fff;background:linear-gradient(135deg,#7b4bff,#e0457b)}
.dav img{width:100%;height:100%;object-fit:cover}
.dside{display:flex;flex-direction:column;align-items:center;gap:12px;position:fixed;left:8px;top:72px;bottom:98px;width:80px;padding:14px 8px;background:#121212;border-radius:8px;overflow-y:auto;scrollbar-width:none;z-index:10}
.dside::-webkit-scrollbar{display:none}
.dsb{width:48px;height:40px;border:0;background:none;color:#b3b3b3;display:flex;align-items:center;justify-content:center;padding:0;flex:none;border-radius:50%}
.dsb:hover{color:#fff}
.dsb svg{width:26px;height:26px;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
.dsc{width:56px;height:56px;border-radius:6px;object-fit:cover;background:#2a2a2a;flex:none;cursor:pointer;display:block}
.dsc:hover{filter:brightness(1.15)}
.dsh{width:56px;height:56px;border-radius:6px;flex:none;cursor:pointer;display:flex;align-items:center;justify-content:center;background:linear-gradient(135deg,#4a2bff,#8fb7ff)}
.dsh svg{width:24px;height:24px}
.dmain{position:fixed;left:96px;right:8px;top:72px;bottom:98px;overflow-y:auto;border-radius:8px;background:linear-gradient(180deg,#2c3a3c 0,#171717 320px,#121212 100%);scrollbar-width:thin;scrollbar-color:#555 transparent}
body.rp .dmain{right:356px}
.home,.card{max-width:none;margin:0;padding:18px 24px 28px}
.card{background:none;box-shadow:none;border-radius:0}
.card .head,.sbox{display:none}
.card .stat{margin:0 0 14px}
.htop .hav{display:none}
.htop{padding-bottom:18px}
.chip{background:#ffffff1a;font-weight:500}
.chip:hover{background:#ffffff2e}
.chip.on{background:#fff;color:#000}
.hgrid{grid-template-columns:repeat(auto-fill,minmax(230px,1fr))}
.ht{height:64px;border-radius:6px;background:#ffffff1a}
.ht:hover{background:#ffffff33}
.ht .hcv,.ht .hart{width:64px;height:64px}
.ht span{font-size:14px}
.hh{font-size:24px;margin:34px 0 14px}
.hhead .hh{margin:34px 0 14px}
.hall{display:block;border:0;background:none;color:#b3b3b3;font-weight:700;font-size:13px;font-family:inherit;padding:0}
.hall:hover{text-decoration:underline;color:#fff}
.dsk{display:block}
.hscroll{overflow:hidden;margin:0 -12px;padding:0;gap:8px;flex-wrap:nowrap}
.hscroll.all{flex-wrap:wrap;row-gap:22px}
.hc{width:176px;padding:12px;border-radius:8px;margin:-12px 0}
.hc:hover{background:#ffffff14}
.hc .hcc{width:152px;height:152px}
.hca .hcc{border-radius:50%}
.hca .hn{margin-top:12px}
.hrows{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:0 24px}
.hr{padding:7px 8px;border-radius:6px}
.hr:hover{background:#ffffff14}
#list,#glist,#pllist{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:0 20px}
#list .empty,#glist .empty,#pllist .empty{grid-column:1/-1}
.pctl{max-width:560px}
.np{left:auto;right:8px;top:72px;bottom:98px;width:340px;border-radius:8px;box-shadow:none}
.np.closed{transform:translateX(112%);opacity:0}
.npin{max-width:none;padding-bottom:18px}
.nphero{height:340px}
.npprog,.npctl{display:none}
.npcard{margin:12px 12px 0}
.toast{bottom:112px}
.dbar{display:grid;grid-template-columns:30% 1fr 30%;align-items:center;position:fixed;left:0;right:0;bottom:0;height:90px;padding:0 16px;background:#000;z-index:30}
.dl{display:flex;align-items:center;gap:12px;min-width:0}
.dcv{width:58px;height:58px;border-radius:4px;object-fit:cover;background:#2a2a2a;flex:none;cursor:pointer}
.dtx{min-width:0}
.dt{font-size:15px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.da{font-size:13px;color:#b3b3b3;margin-top:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.dc{display:flex;flex-direction:column;align-items:center;gap:4px;min-width:0}
.dctl{display:flex;align-items:center;gap:14px}
.dbtn{border:0;background:none;color:#b3b3b3;width:34px;height:34px;padding:0;display:flex;align-items:center;justify-content:center;flex:none}
.dbtn:hover:not(:disabled){color:#fff}
.dbtn.on{color:#1ed760}
.dbtn:disabled{opacity:.35}
.dbtn svg{width:20px;height:20px;display:block;fill:currentColor}
.dbtn svg.lp{fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
.dplay{width:36px;height:36px;border-radius:50%;border:0;background:#fff;color:#000;font-size:18px;padding:0;display:flex;align-items:center;justify-content:center;flex:none}
.dplay:hover{transform:scale(1.06)}
.dplay svg{width:1em;height:1em;fill:currentColor;display:block}
.dprog{display:flex;align-items:center;gap:10px;width:100%;max-width:620px;font-size:12px;color:#a7a7a7}
.dprog span{min-width:36px;text-align:center}
.dprog .barw{flex:1;padding:7px 0}
.dprog .barw:hover .bar i{background:#1ed760}
.dr{display:flex;align-items:center;justify-content:flex-end;gap:8px}
.dr input{width:100px;accent-color:#fff}
}

/* ===== Playlist ala Spotify, hover, antrean, menu, kontrol ===== */
@property --hg{syntax:"<color>";inherits:true;initial-value:#2c3a3c}
.card.t-pl .stat{display:none}
.plh{display:flex;flex-direction:column;align-items:center;text-align:center;gap:14px;margin:8px 0 0;padding:20px 12px 6px;border-radius:18px;background:linear-gradient(180deg,var(--plc,#4a3a78) -40%,transparent 100%)}
.plcov{width:176px;height:176px;border-radius:6px;overflow:hidden;box-shadow:0 8px 28px rgba(0,0,0,.5);background:#2a2a2a;flex:none;display:flex}
.plcov img{width:100%;height:100%;object-fit:cover;display:block}
.plcov.mos{display:grid;grid-template-columns:1fr 1fr;grid-template-rows:1fr 1fr}
.plcov.hrt{align-items:center;justify-content:center;background:linear-gradient(135deg,#4a2bff,#8fb7ff)}
.plcov.hrt svg{width:38%;height:38%}
.pltype{font-size:12px;font-weight:700}
.pltitle{margin:4px 0 8px;font-size:30px;font-weight:900;letter-spacing:-.8px;line-height:1.1}
.plmeta{font-size:13px;color:#d0d0d0}
.plact{display:flex;align-items:center;gap:18px;padding:14px 0 8px}
.plbig{width:54px;height:54px;border-radius:50%;border:0;background:#1ed760;color:#000;font-size:24px;padding:0;display:flex;align-items:center;justify-content:center;flex:none;transition:transform .12s}
.plbig:hover{transform:scale(1.06)}
.plbig:active{transform:scale(.97)}
.plbig svg{width:1em;height:1em;fill:currentColor;display:block}
.pab{position:relative;border:0;background:none;color:#b3b3b3;width:40px;height:40px;padding:0;display:flex;align-items:center;justify-content:center;flex:none}
.pab:hover{color:#fff}
.pab.on{color:#1ed760}
.pab svg{width:24px;height:24px;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round;display:block}
.pab.one::after,.npb.one::after,.dbtn.one::after{content:"1";position:absolute;left:50%;top:50%;transform:translate(-50%,-46%);font-size:8px;font-weight:900;color:inherit}
.npb.one,.dbtn.one{position:relative}
.plhead{display:none}
.pr{display:grid;grid-template-columns:minmax(0,1fr) 40px;align-items:center;gap:8px;padding:6px 4px;border-radius:6px;cursor:pointer}
.pr:active{background:#ffffff14}
.pr .pn,.pr .pd{display:none}
.pr .ptb{display:flex;align-items:center;gap:12px;min-width:0}
.pr .pcv{width:44px;height:44px;border-radius:4px;object-fit:cover;background:#2a2a2a;flex:none}
.pr .tx{min-width:0;flex:1}
.pr.on .t{color:#1ed760}
.pp{display:none;width:16px;height:16px;fill:#fff}
.eq{display:none;gap:2px;align-items:flex-end;height:14px}
.eq i{display:block;width:3px;height:4px;background:#1ed760;animation:eqa 1s ease-in-out infinite}
.eq i:nth-child(2){animation-delay:.2s}
.eq i:nth-child(3){animation-delay:.4s}
@keyframes eqa{0%,100%{height:4px}50%{height:14px}}
.pr.on .pnn{color:#1ed760}
.pr.pg .pnn,.pr.pg .pp{display:none!important}
.pr.pg .eq{display:flex}
.hcw{position:relative;display:block}
.ht{position:relative}
.hpb{position:absolute;right:8px;bottom:8px;width:44px;height:44px;border-radius:50%;background:#1ed760;color:#000;display:flex;align-items:center;justify-content:center;opacity:0;transform:translateY(8px);transition:opacity .25s ease,transform .25s ease;box-shadow:0 8px 12px rgba(0,0,0,.35);pointer-events:none}
.hpb svg{width:20px;height:20px;fill:currentColor;display:block}
.ht .hpb{top:10px;bottom:auto;right:10px}
@media(hover:hover) and (min-width:1000px){.hc:hover .hpb,.ht:hover .hpb{opacity:1;transform:none}}
.sk{display:flex;align-items:center;gap:12px;padding:8px 6px}
.skb{background:linear-gradient(90deg,#222 0,#343434 50%,#222 100%);background-size:220% 100%;animation:shim 1.3s linear infinite;border-radius:6px}
@keyframes shim{from{background-position:120% 0}to{background-position:-100% 0}}
.sk .skc{width:66px;height:66px;flex:none}
.sk .skt{flex:1}
.skl{height:12px;border-radius:6px;margin:7px 0}
.hc .skl{width:80%}
.toast.ok{display:flex;align-items:center;gap:10px}
.toast.ok::before{content:"\2713";width:20px;height:20px;border-radius:50%;background:#1ed760;color:#000;font-size:12px;font-weight:900;display:flex;align-items:center;justify-content:center;flex:none}
.cmb{position:fixed;left:0;top:0;right:0;bottom:0;z-index:79;background:rgba(0,0,0,.55)}
.cm{position:fixed;left:0;right:0;bottom:0;z-index:80;background:#282828;border-radius:16px 16px 0 0;padding:8px 8px calc(14px + env(safe-area-inset-bottom,0px));animation:sheet .25s cubic-bezier(.22,1,.36,1)}
@keyframes sheet{from{transform:translateY(100%)}to{transform:none}}
.cmh{display:flex;align-items:center;gap:12px;padding:10px 10px 12px;margin-bottom:6px;border-bottom:1px solid #ffffff1a}
.cmh .cmc{width:48px;height:48px;border-radius:4px;object-fit:cover;flex:none;background:#333}
.cmh .tx{min-width:0;flex:1}
.cmi{display:block;width:100%;text-align:left;border:0;background:none;color:#fff;padding:14px 12px;font-size:15px;font-weight:500;border-radius:6px;font-family:inherit}
.cmi:active{background:#3e3e3e}
.qp{position:fixed;left:0;top:0;right:0;bottom:0;z-index:55;background:#121212;overflow-y:auto;transition:transform .32s cubic-bezier(.22,1,.36,1),opacity .25s ease-out;-webkit-overflow-scrolling:touch}
.qp.closed{transform:translateY(100%);opacity:0;visibility:hidden;pointer-events:none;transition:transform .28s cubic-bezier(.4,0,1,1),opacity .28s ease-in,visibility 0s linear .28s}
.qh{display:flex;align-items:center;justify-content:space-between;padding:calc(10px + env(safe-area-inset-top,0px)) 14px 8px;font-size:20px;font-weight:800;position:sticky;top:0;background:#121212;z-index:2}
.qb{padding:0 16px 40px;max-width:480px;margin:0 auto}
.qs{font-size:16px;font-weight:800;margin:18px 0 8px;display:flex;justify-content:space-between;align-items:center}
.qs button{border:0;background:none;color:#b3b3b3;font-size:13px;font-weight:700;font-family:inherit}
.qr{display:flex;align-items:center;gap:12px;padding:6px 0;cursor:pointer}
.qr .qc{width:44px;height:44px;border-radius:4px;object-fit:cover;background:#2a2a2a;flex:none}
.qr .tx{min-width:0;flex:1}
.qr.now .t{color:#1ed760}
.qr .hmore{width:32px}
.barw{touch-action:pan-y}
.bar i{border-radius:2px;position:relative}
.barw.drag .bar,.dprog .bar,.np .bar{overflow:visible}
.barw.drag .bar i::after{content:"";position:absolute;right:-6px;top:50%;margin-top:-6px;width:12px;height:12px;border-radius:50%;background:#fff}
@media(hover:hover){.barw:hover .bar i::after{content:"";position:absolute;right:-6px;top:50%;margin-top:-6px;width:12px;height:12px;border-radius:50%;background:#fff}}
.btip{position:absolute;bottom:24px;transform:translateX(-50%);background:#282828;color:#fff;font-size:12px;padding:3px 8px;border-radius:4px;pointer-events:none;white-space:nowrap;z-index:5}
.nphero{touch-action:pan-y}
@media(hover:none){.ll,.lfl{filter:none!important}}
@media(min-width:1000px){
.dmain{--hg:#2c3a3c;background:linear-gradient(180deg,var(--hg) 0,#171717 320px,#121212 100%);transition:--hg .7s ease}
#pllist{display:block}
.plh{flex-direction:row;align-items:flex-end;text-align:left;gap:24px;margin:-18px -24px 0;padding:36px 24px 24px;border-radius:0;background:linear-gradient(180deg,var(--plc,#4a3a78) 0,transparent 100%)}
.plcov{width:200px;height:200px}
.pltype{font-size:13px}
.pltitle{font-size:clamp(34px,5vw,72px);letter-spacing:-2px;margin:8px 0 14px}
.plmeta{font-size:14px}
.plact{padding:20px 0 14px}
.plbig{width:56px;height:56px}
.plhead,.pr{display:grid;grid-template-columns:40px minmax(0,1fr) 72px 44px;gap:12px;align-items:center}
.plhead{padding:0 8px 8px;border-bottom:1px solid #ffffff1a;color:#b3b3b3;font-size:12px;letter-spacing:.8px;text-transform:uppercase;margin-bottom:8px}
.plhead span:first-child{text-align:center}
.plhead .pld{text-align:right}
.pr{padding:6px 8px;height:58px}
.pr:hover{background:#ffffff14}
.pr .pn{display:flex;justify-content:center;align-items:center;color:#b3b3b3;font-size:15px}
.pr .pd{display:block;text-align:right;color:#b3b3b3;font-size:14px}
.pr:hover .pnn{display:none}
.pr:hover .pp{display:block}
.pr .hmore{opacity:0}
.pr:hover .hmore{opacity:1}
.cmb{background:transparent}
.cm{left:auto;right:auto;bottom:auto;min-width:240px;border-radius:6px;padding:4px;box-shadow:0 16px 24px rgba(0,0,0,.5);animation:none}
.cmh{display:none}
.cmi{padding:11px 12px;font-size:14px;color:#e8e8e8}
.cmi:hover{background:#3e3e3e;color:#fff}
.qp{left:auto;right:8px;top:72px;bottom:98px;width:340px;border-radius:8px;z-index:52}
.qp.closed{transform:translateX(112%)}
.qb{max-width:none;padding:0 16px 24px}
.qh{padding-top:14px;font-size:18px}
.dprog .barw{position:relative}
}

/* ===== Font, halaman artis, pencarian, lirik layar penuh, pengaturan ===== */
html,body,button,input,textarea,select{font-family:"DM Sans","Circular Std","Segoe UI",Roboto,system-ui,-apple-system,sans-serif}
.card.t-art .stat{display:none}
.hgreet{font-size:26px;font-weight:800;letter-spacing:-.5px;margin:2px 0 16px}
.hav,.dav{cursor:pointer}
.plh.arh{position:relative}
.arback{position:absolute;left:10px;top:10px;width:38px;height:38px;border-radius:50%;border:0;background:rgba(0,0,0,.45);color:#fff;display:flex;align-items:center;justify-content:center;padding:0;z-index:2}
.arback svg{width:22px;height:22px;fill:none;stroke:currentColor;stroke-width:2.4;stroke-linecap:round;stroke-linejoin:round}
.plcov.arav{border-radius:50%}
.fbtn{border:1px solid #7c7c7c;background:none;color:#fff;border-radius:999px;height:34px;padding:0 16px;font-size:13px;font-weight:700;font-family:inherit}
.fbtn:hover{border-color:#fff;transform:scale(1.03)}
.fbtn.on{border-color:#fff}
.sfl{display:flex;gap:8px;margin:2px 0 14px;overflow-x:auto;scrollbar-width:none}
.sfl::-webkit-scrollbar{display:none}
.tpc{position:relative;display:flex;flex-direction:column;gap:10px;background:#181818;border-radius:10px;padding:16px;cursor:pointer;max-width:420px;transition:background .2s}
.tpc:hover{background:#252525}
.tpc img{width:92px;height:92px;border-radius:6px;object-fit:cover;background:#2a2a2a;box-shadow:0 8px 24px rgba(0,0,0,.45)}
.tpc.art img{border-radius:50%}
.tpc .tt{font-size:28px;font-weight:800;letter-spacing:-.5px;line-height:1.1;overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;word-break:break-word}
.tpc .tk{display:inline-block;font-size:12px;font-weight:700;background:#121212;border-radius:999px;padding:4px 12px;width:max-content;max-width:100%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.tpc .hpb{right:16px;bottom:16px}
@media(hover:none){.tpc .hpb{opacity:1;transform:none}}
.xh{display:flex;justify-content:space-between;align-items:center;margin:20px 0 10px;font-size:18px;font-weight:800}
.xh button{border:0;background:none;color:#b3b3b3;font-size:13px;font-weight:700;font-family:inherit}
.hrw{display:flex;align-items:center;gap:12px;padding:10px 4px;cursor:pointer;border-radius:6px}
.hrw:active{background:#ffffff14}
.hrw svg{width:20px;height:20px;fill:none;stroke:#b3b3b3;stroke-width:2;stroke-linecap:round;flex:none}
.hrw span{flex:1;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-size:15px}
.hrw .hx{border:0;background:none;color:#b3b3b3;padding:4px 8px;font-size:18px;flex:none}
.xg{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.xt{position:relative;height:96px;border-radius:8px;padding:12px;overflow:hidden;cursor:pointer;font-size:17px;font-weight:800;letter-spacing:-.3px;line-height:1.15}
.xt span{position:absolute;right:-4px;bottom:-4px;font-size:44px;transform:rotate(22deg);filter:drop-shadow(0 4px 8px rgba(0,0,0,.35))}
.xt:active{transform:scale(.98)}
.arr{display:flex;align-items:center;gap:12px;padding:8px 4px;cursor:pointer;border-radius:6px}
.arr:active{background:#ffffff14}
.arr img{width:56px;height:56px;border-radius:50%;object-fit:cover;background:#2a2a2a;flex:none}
.arr b{display:block;font-size:16px}
.arr small{color:#b3b3b3;font-size:13px}
.lyfs{position:fixed;left:0;top:0;right:0;bottom:0;z-index:58;background:var(--lfc,#5a1f3a);display:flex;flex-direction:column;color:#fff;transition:transform .35s cubic-bezier(.22,1,.36,1),opacity .3s ease,background .6s ease}
.lyfs.closed{transform:translateY(100%);opacity:0;visibility:hidden;pointer-events:none;transition:transform .3s cubic-bezier(.4,0,1,1),opacity .3s,visibility 0s linear .3s}
.lfh{display:flex;align-items:center;gap:10px;padding:calc(10px + env(safe-area-inset-top,0px)) 12px 10px;background:linear-gradient(180deg,rgba(0,0,0,.2),transparent)}
.lfh .lft{flex:1;min-width:0;text-align:center}
.lfh b{display:block;font-size:15px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.lfh .la{display:block;font-size:12px;opacity:.75;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.lfb{flex:1;overflow-y:auto;padding:22vh 22px 38vh;-webkit-overflow-scrolling:touch;scrollbar-width:none}
.lfb::-webkit-scrollbar{display:none}
.lfl{font-size:28px;font-weight:800;line-height:1.22;margin:16px 0;color:rgba(255,255,255,.55);transform-origin:left center;cursor:pointer;transition:color .45s ease,transform .5s cubic-bezier(.22,1,.36,1),opacity .45s ease,filter .45s ease}
.lfl.cur{color:#fff}
.lfl.st{color:rgba(255,255,255,.92);cursor:default}
.lff{padding:6px 22px calc(18px + env(safe-area-inset-bottom,0px));background:linear-gradient(0deg,rgba(0,0,0,.28),transparent)}
.lftm{display:flex;justify-content:space-between;font-size:12px;opacity:.85;margin-top:2px}
.lfc{display:flex;justify-content:center;align-items:center;gap:26px;margin-top:6px}
.lfopen{border:0;background:none;color:#fff;padding:0;width:28px;height:28px;display:flex;align-items:center;justify-content:center;opacity:.85}
.lfopen svg{width:18px;height:18px;fill:none;stroke:currentColor;stroke-width:2.2;stroke-linecap:round;stroke-linejoin:round}
.npcard h4{display:flex;align-items:center;justify-content:space-between}
.cmi.on{color:#1ed760}
.bd{position:absolute;right:-3px;top:-3px;min-width:16px;height:16px;border-radius:8px;background:#1ed760;color:#000;font-size:10px;font-weight:800;display:flex;align-items:center;justify-content:center;padding:0 3px}
#dsleep,#npsleep{position:relative}
@media(min-width:1000px){
.xg{grid-template-columns:repeat(auto-fill,minmax(190px,1fr))}
.xt{height:120px;font-size:20px;padding:16px}
.xt span{font-size:56px}
.hgreet{font-size:30px}
.lyfs{left:96px;right:8px;top:72px;bottom:98px;border-radius:8px;z-index:53}
.lfl{font-size:38px}
.lfb{padding:20vh 8% 36vh}
.lff{display:none}
}
</style></head>
<body>
<div class="dtop" id="dtop">
  <button class="dhome on" id="dhome" aria-label="Home"><svg viewBox="0 0 24 24"><path d="M4 10.5L12 4l8 6.5V20h-5.5v-6h-5v6H4z"/></svg></button>
  <div class="dsearch"><svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="6.5"/><path d="M16 16l4.5 4.5"/></svg><input id="dq" type="search" placeholder="Apa yang ingin kamu putar?" autocomplete="off"></div>
  <div class="dav" id="dav"></div>
</div>
<div class="dside" id="dside"></div>
<div class="dmain" id="dmain">
<div class="home" id="home">
  <div class="htop">
    <div class="hav" id="hav"></div>
    <button class="chip on" data-c="all">Semua</button>
    <button class="chip" data-c="mus">Musik</button>
    <button class="chip" data-c="pod">Podcast</button>
  </div>
  <div id="hbody"></div>
</div>
<div class="card hide">
  <div class="head">
    <div class="brand">
      <svg class="logo" viewBox="0 0 48 48" aria-hidden="true"><circle cx="24" cy="24" r="24" fill="#1db954"/>
        <g fill="none" stroke="#000" stroke-linecap="round"><path d="M10.6 17.4c8.6-2.6 20.6-2.1 28 2.4" stroke-width="4.2"/><path d="M12.2 24.8c7-2 15.8-1.4 22 2.3" stroke-width="3.5"/><path d="M13.6 31.6c5.7-1.6 11.8-1.1 16.7 1.8" stroke-width="2.9"/></g></svg>
      <div><div class="name">Spotify<span class="rg">&reg;</span></div><div class="sub" id="who">Pemutar lagu</div></div>
    </div>
    <div class="live">LIVE</div>
  </div>
  <div class="tabs">
    <button class="tab on" id="t-cari">Cari</button>
    <button class="tab" id="t-global">Ruang Global</button>
    <button class="tab" id="t-pl">Playlist</button>
  </div>
  <div class="stat"><span class="dot" id="dot"></span><span id="st">Siap. Cari lagu di atas.</span></div>
  <div id="p-cari">
    <div class="sbox">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#a7a7a7" stroke-width="2.2" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/></svg>
      <input id="q" type="search" placeholder="Cari lagu atau artis" autocomplete="off" enterkeyhint="search">
    </div>
    <div class="sfl hide" id="sfl"><button class="chip on" data-f="all">Semua</button><button class="chip" data-f="song">Lagu</button><button class="chip" data-f="artist">Artis</button></div>
    <div id="sex" class="hide"></div>
    <div id="stop"></div>
    <div id="sart" class="hide"></div>
    <div class="list" id="list"></div>
    <div class="pager hide" id="pgr"><button id="prev" aria-label="Sebelumnya"><svg class="si" viewBox="0 0 24 24"><path d="M6 15l6-6 6 6"/></svg></button><span id="pg">1/1</span><button id="next" aria-label="Berikutnya"><svg class="si" viewBox="0 0 24 24"><path d="M6 9l6 6 6-6"/></svg></button></div>
  </div>
  <div id="p-global" class="hide"><div class="list" id="glist"></div></div>
  <div id="p-art" class="hide"><div id="arbody"></div></div>
  <div id="p-pl" class="hide">
    <div class="plh" id="plh">
      <div class="plcov" id="plcov"></div>
      <div class="plin"><div class="pltype">Playlist</div><h1 class="pltitle">Playlist Kamu</h1><div class="plmeta" id="plmeta"></div></div>
    </div>
    <div class="plact">
      <button class="plbig" id="pl-o" aria-label="Putar"></button>
      <button class="pab" id="pl-r" aria-label="Acak"><svg viewBox="0 0 24 24"><path d="M16 3h5v5M4 20L21 3M21 16v5h-5M15 15l6 6M4 4l5 5"/></svg></button>
      <button class="pab" id="pl-l" aria-label="Ulang"><svg viewBox="0 0 24 24"><path d="M17 2l4 4-4 4M3 11V9a3 3 0 013-3h15M7 22l-4-4 4-4M21 13v2a3 3 0 01-3 3H3"/></svg></button>
      <button class="pab" id="pl-c" aria-label="Kosongkan playlist"><svg viewBox="0 0 24 24"><path d="M3 6h18M8 6V4h8v2M6 6l1 14h10l1-14M10 11v5M14 11v5"/></svg></button>
    </div>
    <div class="plhead"><span>#</span><span>Judul</span><span class="pld"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg></span><span></span></div>
    <div class="list" id="pllist"></div>
    <div class="pager hide" id="plpgr"><button id="plprev" aria-label="Sebelumnya"><svg class="si" viewBox="0 0 24 24"><path d="M6 15l6-6 6 6"/></svg></button><span id="plpg">1/1</span><button id="plnext" aria-label="Berikutnya"><svg class="si" viewBox="0 0 24 24"><path d="M6 9l6 6 6-6"/></svg></button></div>
  </div>
</div>
</div>
  <div class="player hide" id="pl">
    <img class="cv" id="pcv" alt="">
    <div class="tx"><div class="t" id="pt"></div><div class="a" id="pa"></div><div class="barw" id="pbarw"><div class="bar"><i id="pbar"></i></div></div><div class="a" id="ptime"></div></div>
    <button class="pbtn sm hide" id="pprev" aria-label="Lagu sebelumnya"><svg viewBox="0 0 24 24"><path d="M6 5h2.4v14H6zM20 5v14L9.5 12z"/></svg></button>
    <button class="pbtn" id="pbtn" aria-label="Putar atau jeda"><svg viewBox="0 0 24 24"><path d="M8 4.7c0-.8.9-1.3 1.6-.9l10 6.3c.6.4.6 1.4 0 1.8l-10 6.3c-.7.4-1.6-.1-1.6-.9z"/></svg></button>
    <button class="pbtn sm hide" id="pnext" aria-label="Lagu berikutnya"><svg viewBox="0 0 24 24"><path d="M15.6 5H18v14h-2.4zM4 5v14l10.5-7z"/></svg></button>
  </div>
<nav class="bnav" id="bnav"><div class="bin">
  <button class="on" data-t="home"><svg viewBox="0 0 24 24"><path class="f" d="M4 10.5L12 4l8 6.5V20h-5.5v-6h-5v6H4z"/></svg><span>Home</span></button>
  <button data-t="cari"><svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="6.5"/><path d="M16 16l4.5 4.5"/></svg><span>Cari</span></button>
  <button data-t="pl"><svg viewBox="0 0 24 24"><path d="M5 4v16M10 4v16M15 5.5l4.5 14.5"/></svg><span>Koleksi Kamu</span></button>
  <button data-t="global"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3.2 3.4 3.2 14.6 0 18M12 3c-3.2 3.4-3.2 14.6 0 18"/></svg><span>Global</span></button>
</div></nav>
<div class="dbar" id="dbar">
  <div class="dl">
    <img class="dcv" id="dcv" alt="" style="visibility:hidden">
    <div class="dtx"><div class="dt" id="dt"></div><div class="da" id="da"></div></div>
    <button class="addb" id="dadd" aria-label="Playlist" style="visibility:hidden"></button>
  </div>
  <div class="dc">
    <div class="dctl">
      <button class="dbtn" id="dshuf" aria-label="Putar acak"><svg class="lp" viewBox="0 0 24 24"><path d="M16 3h5v5M4 20L21 3M21 16v5h-5M15 15l6 6M4 4l5 5"/></svg></button>
      <button class="dbtn" id="dprev" aria-label="Sebelumnya"><svg viewBox="0 0 24 24"><path d="M6 5h2.4v14H6zM20 5v14L9.5 12z"/></svg></button>
      <button class="dplay" id="dplay" aria-label="Putar atau jeda"></button>
      <button class="dbtn" id="dnext" aria-label="Berikutnya"><svg viewBox="0 0 24 24"><path d="M15.6 5H18v14h-2.4zM4 5v14l10.5-7z"/></svg></button>
      <button class="dbtn" id="dloop" aria-label="Ulang playlist"><svg class="lp" viewBox="0 0 24 24"><path d="M17 2l4 4-4 4M3 11V9a3 3 0 013-3h15M7 22l-4-4 4-4M21 13v2a3 3 0 01-3 3H3"/></svg></button>
    </div>
    <div class="dprog"><span id="dcur">0:00</span><div class="barw" id="dbarw"><div class="bar"><i id="dbarfill"></i></div><div class="btip hide" id="dtip"></div></div><span id="ddur">0:00</span></div>
  </div>
  <div class="dr">
    <button class="dbtn" id="dpanel" aria-label="Tampilan sedang diputar"><svg class="lp" viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M15 4v16"/></svg></button>
    <button class="dbtn" id="dsleep" aria-label="Timer tidur"><svg class="lp" viewBox="0 0 24 24"><path d="M20 14.5A8 8 0 019.5 4a8 8 0 1010.5 10.5z"/></svg><span class="bd hide" id="dsb"></span></button>
    <button class="dbtn" id="dqueue" aria-label="Antrean"><svg class="lp" viewBox="0 0 24 24"><path d="M4 6h12M4 12h12M4 18h8M18 14v6l4-3z"/></svg></button>
    <button class="dbtn" id="dmute" aria-label="Bisukan"></button>
    <input id="dvol" type="range" min="0" max="100" value="100" aria-label="Volume">
  </div>
</div>
<div class="toast hide" id="toast"></div>
<div class="np closed" id="np">
  <div class="npin">
    <div class="nphero" id="nphero">
      <canvas class="npbg" id="npbg" width="16" height="16"></canvas>
      <canvas class="npvid" id="npcv"></canvas>
      <div class="nptop">
        <button class="npb" id="npx" aria-label="Tutup"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9l6 6 6-6"/></svg></button>
        <span>Sedang diputar</span>
        <button class="npb" id="npq" aria-label="Antrean"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 6h12M4 12h12M4 18h8M18 14v6l4-3z"/></svg></button>
      </div>
      <div class="npmeta">
        <div class="nm"><div class="npt" id="npt"></div><div class="npa" id="npa"></div></div>
        <button class="npb" id="npsleep" aria-label="Timer tidur"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 14.5A8 8 0 019.5 4a8 8 0 1010.5 10.5z"/></svg><span class="bd hide" id="npsb"></span></button>
        <button class="npb" id="npshare" aria-label="Bagikan"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 15V4M8 8l4-4 4 4M5 13v6h14v-6"/></svg></button>
        <button class="addb" id="npadd" aria-label="Tambah ke playlist"></button>
      </div>
    </div>
    <div class="npprog"><div class="barw" id="npbarw"><div class="bar"><i id="npbar"></i></div></div><div class="nptm"><span id="npcur">0:00</span><span id="npdur"></span></div></div>
    <div class="npctl">
      <button class="npb" id="npshuf" aria-label="Acak"><svg class="lp" viewBox="0 0 24 24"><path d="M16 3h5v5M4 20L21 3M21 16v5h-5M15 15l6 6M4 4l5 5"/></svg></button>
      <button class="npb" id="npprev" aria-label="Lagu sebelumnya"><svg viewBox="0 0 24 24"><path d="M6 5h2.4v14H6zM20 5v14L9.5 12z"/></svg></button>
      <button class="npb npplay" id="npplay" aria-label="Putar atau jeda"><svg viewBox="0 0 24 24"><path d="M8 4.7c0-.8.9-1.3 1.6-.9l10 6.3c.6.4.6 1.4 0 1.8l-10 6.3c-.7.4-1.6-.1-1.6-.9z"/></svg></button>
      <button class="npb" id="npnext" aria-label="Lagu berikutnya"><svg viewBox="0 0 24 24"><path d="M15.6 5H18v14h-2.4zM4 5v14l10.5-7z"/></svg></button>
      <button class="npb" id="nploop" aria-label="Ulang playlist"><svg class="lp" viewBox="0 0 24 24"><path d="M17 2l4 4-4 4M3 11V9a3 3 0 013-3h15M7 22l-4-4 4-4M21 13v2a3 3 0 01-3 3H3"/></svg></button>
    </div>
    <div class="npcard hide" id="nplyr"><h4><span>Pratinjau lirik</span><button class="lfopen" id="lfopen" aria-label="Lirik layar penuh"><svg viewBox="0 0 24 24"><path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/></svg></button></h4><div class="nplines" id="nplines"></div></div>
    <div class="npcard npart"><h4>Tentang artis</h4><div class="arow"><img id="npai" alt=""><b id="npar"></b><button id="npmore">Lagu lainnya</button></div></div>
  </div>
</div>
<div class="qp closed" id="qp"><div class="qh"><span>Antrean</span><button class="npb" id="qx" aria-label="Tutup"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18"/></svg></button></div><div class="qb" id="qb"></div></div>
<div class="lyfs closed" id="lyfs">
  <div class="lfh"><button class="npb" id="lfx" aria-label="Tutup"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9l6 6 6-6"/></svg></button><div class="lft"><b id="lft"></b><span class="la" id="lfa"></span></div><span style="width:40px"></span></div>
  <div class="lfb" id="lfb"><div class="lfi" id="lfi"></div></div>
  <div class="lff">
    <div class="barw" id="lfbarw"><div class="bar"><i id="lfbar"></i></div></div>
    <div class="lftm"><span id="lfcur">0:00</span><span id="lfdur"></span></div>
    <div class="lfc"><button class="npb" id="lfprev" aria-label="Sebelumnya"><svg viewBox="0 0 24 24"><path d="M6 5h2.4v14H6zM20 5v14L9.5 12z"/></svg></button><button class="npb npplay" id="lfplay" aria-label="Putar atau jeda"></button><button class="npb" id="lfnext" aria-label="Berikutnya"><svg viewBox="0 0 24 24"><path d="M15.6 5H18v14h-2.4zM4 5v14l10.5-7z"/></svg></button></div>
  </div>
</div>
<video class="vhid" id="npvid" muted playsinline webkit-playsinline preload="auto"></video>
<div class="cmb hide" id="cmb"></div>
<div class="cm hide" id="cm"></div>
<script>
(function(){
var tg = window.Telegram && window.Telegram.WebApp;
if (tg) { tg.ready(); tg.expand(); try { tg.setHeaderColor("#171717"); tg.setBackgroundColor("#171717"); } catch (e) {} }
var INIT = tg ? tg.initData : "";
var base = location.pathname; if (base.slice(-1) !== "/") base += "/";
var items = [], page = 1, timer = null, seq = 0;
var $ = function (id) { return document.getElementById(id); };

if (tg && tg.initDataUnsafe && tg.initDataUnsafe.user) $("who").textContent = "Halo, " + (tg.initDataUnsafe.user.first_name || "kamu");

function status(t, ok) { $("st").textContent = t; $("dot").style.background = ok === false ? "#e5484d" : "#1db954"; if (ok === false && (curTab === "home" || curTab === "pl")) toast(t); }
var toastT = null;
function toast(t, ok) { var e = $("toast"); e.textContent = t; e.className = "toast" + (ok ? " ok" : ""); clearTimeout(toastT); toastT = setTimeout(function () { e.className = "toast hide"; }, 3200); }

function api(path, opts) {
  opts = opts || {};
  opts.headers = Object.assign({ "X-Init-Data": INIT }, opts.headers || {});
  return fetch(base + path, opts).then(function (r) {
    return r.json().catch(function () { return {}; }).then(function (j) {
      if (!r.ok) throw new Error(j.error || ("HTTP " + r.status));
      return j;
    });
  });
}

function ago(ts) {
  var s = Math.max(0, Math.floor(Date.now() / 1000 - ts));
  if (s < 60) return "baru saja";
  if (s < 3600) return Math.floor(s / 60) + " mnt lalu";
  if (s < 86400) return Math.floor(s / 3600) + " jam lalu";
  return Math.floor(s / 86400) + " hari lalu";
}

function row(it, subtitle, canAdd) {
  var d = document.createElement("div"); d.className = "it";
  var im = document.createElement("img"); im.className = "cv"; im.loading = "lazy"; im.alt = "";
  im.src = it.cover || BLANK;
  var tx = document.createElement("div"); tx.className = "tx";
  var t = document.createElement("div"); t.className = "t"; t.textContent = it.title;
  var a = document.createElement("div"); a.className = "a"; a.textContent = subtitle || it.artist;
  tx.appendChild(t); tx.appendChild(a); d.appendChild(im); d.appendChild(tx);
  d.addEventListener("click", function () { if (curTab === "cari") addHist(curQuery); play(it); });
  if (canAdd) {
    var b = document.createElement("button"); setAdd(b, inPl(it));
    b.setAttribute("aria-label", "Tambah ke playlist");
    b.addEventListener("click", function (e) { e.stopPropagation(); addPl(it, b); });
    d.appendChild(b);
  }
  var mo = document.createElement("button"); mo.className = "hmore"; mo.innerHTML = DOTS; mo.setAttribute("aria-label", "Opsi lainnya");
  mo.addEventListener("click", function (e) { e.stopPropagation(); openMenu(it, e); });
  d.appendChild(mo); ctx(d, it);
  return d;
}

function uniq(list) {   // satu lagu cukup tampil sekali per orang
  var seen = {}, out = [];
  list.forEach(function (x) { var k = key(x) + "|" + (x.who || ""); if (!seen[k]) { seen[k] = 1; out.push(x); } });
  return out;
}
var psLast = {};
function ps(box) {   // HP: 4 lagu per halaman. Desktop: sebanyak yang muat di ruang kosong, tombol halaman baru muncul kalau sudah penuh
  if (!isDesk() || !box) return 4;
  if (!box.offsetParent) return psLast[box.id] || 12;
  var main = $("dmain"), mr = main.getBoundingClientRect(), br = box.getBoundingClientRect();
  var off = br.top - mr.top + main.scrollTop;
  var row = box.querySelector(".it"), rh = row ? row.offsetHeight : 82;
  var cols = Math.max(1, getComputedStyle(box).gridTemplateColumns.split(" ").length);
  var rows = Math.max(2, Math.floor((main.clientHeight - off - 80) / Math.max(40, rh)));
  return (psLast[box.id] = rows * cols);
}
function primaryArtist(it) { return String(it.artist || "").split(",")[0].trim(); }
function drawSearch() {
  var box = $("list"), has = items.length > 0, fl = sfilter;
  var showEx = !has && !curQuery;
  $("sex").className = showEx ? "" : "hide"; if (showEx) drawExplore();
  $("sfl").className = has ? "sfl" : "sfl hide";
  var chs = $("sfl").children; for (var c = 0; c < chs.length; c++) chs[c].className = "chip" + (chs[c].getAttribute("data-f") === fl ? " on" : "");
  $("sart").className = (has && fl === "artist") ? "" : "hide";
  box.className = fl === "artist" ? "list hide" : "list";
  if (has && fl === "artist") drawArtistsList(); else $("sart")._sig = "";
  drawTop(has && fl === "all");
  var P = ps(box), pages = Math.max(1, Math.ceil(items.length / P));
  if (page > pages) page = pages;
  var vis = items.slice((page - 1) * P, page * P);
  var sig = fl + "|" + curQuery + "|" + vis.map(function (x) { return key(x) + (inPl(x) ? "+" : "-"); }).join("~") + "#" + items.length;
  if (box._sig !== sig) {
    box._sig = sig; box.textContent = "";
    if (!has) {
      if (curQuery) { var e = document.createElement("div"); e.className = "empty"; e.textContent = "Tidak ada hasil untuk \u201C" + curQuery + "\u201D."; box.appendChild(e); }
    } else {
      vis.forEach(function (it) { box.appendChild(row(it, null, true)); });
    }
  }
  $("pgr").className = (has && fl !== "artist" && items.length > P) ? "pager" : "pager hide";
  $("pg").textContent = page + "/" + pages;
  $("prev").disabled = page <= 1; $("next").disabled = page >= pages;
}

var au = new Audio(); au.preload = "auto"; var cur = null, ready = false, pseq = 0, pfDone = false;
var BLANK = "data:image/gif;base64,R0lGODlhAQABAAAAACH5BAEAAAAALAAAAAABAAEAAAIBRAA7";
var SILENT = "data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAIA+AAACABAAZGF0YQAAAAA=";
function fmt(s) { s = Math.max(0, Math.floor(s || 0)); return Math.floor(s / 60) + ":" + ("0" + (s % 60)).slice(-2); }
var IC_PLAY = '<svg viewBox="0 0 24 24"><path d="M8 4.7c0-.8.9-1.3 1.6-.9l10 6.3c.6.4.6 1.4 0 1.8l-10 6.3c-.7.4-1.6-.1-1.6-.9z"/></svg>', IC_PAUSE = '<svg viewBox="0 0 24 24"><rect x="6" y="4" width="4.6" height="16" rx="1.1"/><rect x="13.4" y="4" width="4.6" height="16" rx="1.1"/></svg>';
var IC_ADD = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><circle cx="12" cy="12" r="9.5"/><path d="M12 7.5v9M7.5 12h9"/></svg>';
var IC_DONE = '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" fill="#1ed760"/><path d="M7.4 12.4l3.1 3.1 6.1-6.6" fill="none" stroke="#000" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"/></svg>';
var IC_DEL = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18"/></svg>';
function setAdd(b, on) { b.className = "addb" + (on ? " done" : ""); b.innerHTML = on ? IC_DONE : IC_ADD; }
function setIc(el, on) { var k = on ? "1" : "0"; if (el.getAttribute("data-s") !== k) { el.setAttribute("data-s", k); el.innerHTML = on ? IC_PAUSE : IC_PLAY; } }
function setBtn() { setIc($("pbtn"), ready && !au.paused); npBtn(); dSync(); markPl(); try { if (navigator.mediaSession) navigator.mediaSession.playbackState = (ready && !au.paused) ? "playing" : "paused"; } catch (e) {} }
au.addEventListener("play", setBtn); au.addEventListener("pause", setBtn);
au.addEventListener("timeupdate", function () {
  if (!ready || !au.duration || !isFinite(au.duration) || seeking) return;
  $("pbar").style.width = (au.currentTime / au.duration * 100) + "%";
  if ((plMode || queue.length) && !pfDone && au.currentTime > 1) { pfDone = true; prefetchNext(); }
  if (cf > 0 && !cfDone && !repOne && !sleepEnd && au.duration > cf * 2 + 5 && au.duration - au.currentTime <= cf && (queue.length || (plMode && (plLoop || plPos < plOrder.length - 1)))) startCrossfade();
  $("ptime").textContent = fmt(au.currentTime) + " / " + fmt(au.duration);
  npTime();
});
au.addEventListener("ended", function () { if (!ready || !(au.duration > 1) || String(au.src).indexOf("data:") === 0) return; setBtn(); if (sleepEnd) { clearSleep(); toast("Timer tidur: pemutaran berhenti", true); status("Timer tidur: pemutaran berhenti."); return; } if (queue.length || plMode) { skipNext(); return; } status("Selesai. Ketuk \u25B6 untuk mengulang atau pilih lagu lain."); });
au.addEventListener("error", function () { if (ready) status("Audio tidak bisa diputar di perangkat ini.", false); });
$("pbtn").addEventListener("click", function () {
  if (!cur || !ready) return;
  if (au.paused) { if (au.ended) au.currentTime = 0; au.play().catch(function () {}); } else au.pause();
});
$("pbarw").addEventListener("click", function (e) {
  if (!ready || !au.duration || !isFinite(au.duration)) return;
  var r = this.getBoundingClientRect();
  au.currentTime = Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)) * au.duration;
});

function showPlayer(it) {
  if (isDesk() && !deskClosed && !npVisible) { npVisible = true; $("np").className = "np"; $("np").scrollTop = 0; setRp(); }
  npTrack(it); dSync(); msSet(it); if (qOpen) drawQueue();
  $("pl").className = "player"; $("pcv").src = it.cover || BLANK; $("pt").textContent = it.title; $("pa").textContent = it.artist;
  $("pbar").style.width = "0"; $("ptime").textContent = "Memuat..."; setBtn();
}
function logPlay(it) {
  api("api/play", { method: "POST", headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ title: it.title, artist: it.artist, cover: it.cover || "" }) }).catch(function () {});
}

function play(it, fromPl) {
  if (!fromPl && plMode) { plMode = false; updNav(); drawPl(); }
  if (!fromPl && cur && cur === it && ready) { if (au.paused) au.play().catch(function () {}); else au.pause(); return; }
  var my = ++pseq; ready = false; cur = it; pfDone = false; cfDone = false;
  au.loop = false; au.src = SILENT; au.play().catch(function () {});   // membuka kunci audio selama ketukan, supaya lagu bisa jalan sendiri setelah siap
  showPlayer(it);
  status("Memuat lagu dari server MP...");
  // tanya server: kalau file lagunya TIDAK ada di server -> "di download", kalau ada -> "memuat"
  var dlT = it.stream ? 0 : setInterval(function () {
    if (my !== pseq || ready) { clearInterval(dlT); return; }
    api("api/phase?title=" + encodeURIComponent(it.title) + "&artist=" + encodeURIComponent(it.artist)).then(function (r) {
      if (my !== pseq || ready) return;
      if (r && r.p === "unduh") { status("Lagu di download dari server MP..."); $("ptime").textContent = "Mengunduh..."; }
      else if (r && r.p === "muat") { status("Memuat lagu dari server MP..."); $("ptime").textContent = "Memuat..."; }
    }).catch(function () {});
  }, 700);
  var job = it.stream ? Promise.resolve({ url: it.stream }) :
    resolveIt(it, 2);
  job.then(function (j) {
    clearInterval(dlT);
    if (my !== pseq) return;
    it.stream = j.url; ready = true; au.src = base + j.url; au.loop = repOne; vSync();
    return au.play().then(function () {
      status("Memutar: " + it.title); plFails = 0;
      if (tg && tg.HapticFeedback) tg.HapticFeedback.impactOccurred("light");
      logPlay(it);
    }).catch(function () { status("Siap. Ketuk tombol \u25B6 untuk memutar.", true); setBtn(); logPlay(it); });
  }).catch(function (e) {
    clearInterval(dlT);
    if (my !== pseq) return;
    if (it.preview) {   // cadangan: cuplikan 30 detik dari iTunes kalau server gagal
      ready = true; au.src = it.preview;
      au.play().then(function () { status("Server gagal, memutar cuplikan 30 detik: " + it.title); logPlay(it); })
        .catch(function () { status("Siap. Ketuk tombol \u25B6 untuk memutar cuplikan.", true); });
      return;
    }
    status("Gagal: " + e.message, false); $("ptime").textContent = "";
    if (plMode) {
      plFails++;
      if (plFails < 3) setTimeout(function () { if (my === pseq && plMode) nextPl(); }, 1500);
      else { plMode = false; updNav(); drawPl(); status("Playlist berhenti: 3 lagu berturut-turut gagal diputar.", false); }
    }
  });
}

function search(q) {
  var my = ++seq; curQuery = q; status("Mencari..."); $("sex").className = "hide"; $("stop").textContent = ""; $("stop")._sig = ""; skel($("list"), 6); $("pgr").className = "pager hide";
  api("api/search?q=" + encodeURIComponent(q)).then(function (j) {
    if (my !== seq) return;
    items = j.items || []; page = 1; drawSearch();
    status(items.length ? "Tersambung. " + items.length + " lagu ditemukan." : "Tidak ada hasil.", items.length > 0);
  }).catch(function (e) { if (my === seq) status("Gagal: " + e.message, false); });
}

$("q").addEventListener("input", function () {
  clearTimeout(timer);
  var q = $("q").value.trim();
  if (!q) { items = []; page = 1; curQuery = ""; drawSearch(); status("Siap. Cari lagu di atas."); return; }
  timer = setTimeout(function () { search(q); }, 600);
});
$("q").addEventListener("keydown", function (e) {
  if (e.key === "Enter") { clearTimeout(timer); var q = $("q").value.trim(); if (q) { addHist(q); search(q); } $("q").blur(); }
});
$("prev").addEventListener("click", function () { if (page > 1) { page--; drawSearch(); } });
$("next").addEventListener("click", function () { page++; drawSearch(); });

var curTab = "home";
function showTab(name) {
  curTab = name;
  if (name !== "art") lastMain = name;
  ["cari", "global", "pl", "art"].forEach(function (n) {
    var tb = $("t-" + n); if (tb) tb.className = "tab" + (name === n ? " on" : "");
    $("p-" + n).className = name === n ? "" : "hide";
  });
  $("home").className = "home" + (name === "home" ? "" : " hide");
  document.querySelector(".card").className = "card" + (name === "home" ? " hide" : " t-" + name); closeMenu();
  var nb = document.querySelectorAll("#bnav button");
  for (var i = 0; i < nb.length; i++) nb[i].className = nb[i].getAttribute("data-t") === (name === "art" ? lastMain : name) ? "on" : "";
  window.scrollTo(0, 0); $("dmain").scrollTop = 0; $("dhome").className = "dhome" + (name === "home" ? " on" : "");
  if (name === "home") { drawHome(); loadHome(); }
  else if (name === "global") loadGlobal();
  else if (name === "pl") { status("Playlist: " + pl.length + " lagu."); drawPl(); loadPl(); }
  else if (name === "art") { /* dirender oleh openArtist */ }
  else { status("Siap. Cari lagu di atas."); drawSearch(); }
}
function loadGlobal() {
  status("Memuat lagu yang baru diputar..."); if (!$("glist").children.length) skel($("glist"), 5);
  api("api/recent").then(function (j) {
    var box = $("glist");
    var list = uniq(j.items || []);
    var sig = list.map(function (x) { return key(x) + x.who + x.ts + ago(x.ts) + (inPl(x) ? "+" : "-"); }).join("~");
    if (box._sig !== sig) {
      box._sig = sig; box.textContent = "";
      if (!list.length) { var e = document.createElement("div"); e.className = "empty"; e.textContent = "Belum ada lagu yang diputar."; box.appendChild(e); }
      list.forEach(function (it) { box.appendChild(row(it, it.artist + " \u00b7 " + it.who + " \u00b7 " + ago(it.ts), true)); });
    }
    status("Tersambung. Ketuk lagu untuk memutarnya juga.");
  }).catch(function (e) { status("Gagal: " + e.message, false); });
}
$("t-cari").addEventListener("click", function () { showTab("cari"); });
$("t-global").addEventListener("click", function () { showTab("global"); });
$("t-pl").addEventListener("click", function () { showTab("pl"); });

// ---------------------------------------------------------------- playlist (tersimpan di server, sama dengan playlist di chat bot)
var pl = [], plKeys = {}, plPage = 1, plOrder = [], plPos = -1, plMode = false, plMix = false, plLoop = false, plFails = 0;
function key(it) { return (it.title + "|" + it.artist).toLowerCase(); }
function inPl(it) { return !!plKeys[key(it)]; }
function rebuildKeys() { plKeys = {}; pl.forEach(function (x) { plKeys[key(x)] = 1; }); }
function postJ(path, obj) { return api(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(obj || {}) }); }
function resolveIt(it, tries, bg) {
  return api("api/resolve?title=" + encodeURIComponent(it.title) + "&artist=" + encodeURIComponent(it.artist) + "&ms=" + (it.ms || 0) + (bg ? "&bg=1" : "")).catch(function (e) {
    if (tries > 0 && /Pelan-pelan/.test(e.message)) return new Promise(function (r) { setTimeout(r, 2300); }).then(function () { return resolveIt(it, tries - 1, bg); });
    throw e;
  });
}
function updNav() {
  $("pprev").className = "pbtn sm" + (plMode ? "" : " hide");
  $("pnext").className = "pbtn sm" + (plMode || queue.length ? "" : " hide");
  dSync();
}
function loadPl() {
  return api("api/pl").then(function (j) { pl = j.items || []; rebuildKeys(); drawPl(); drawSearch(); }).catch(function (e) { status("Gagal memuat playlist: " + e.message, false); });
}
function addPl(it, b) {
  if (inPl(it)) { status("Sudah ada di playlist (" + pl.length + " lagu)."); return; }
  b.disabled = true;
  postJ("api/pladd", { title: it.title, artist: it.artist, ms: it.ms || 0, cover: it.cover || "" }).then(function (j) {
    if (!j.dup) {
      var n = { title: it.title, artist: it.artist, ms: it.ms || 0, cover: it.cover || "", preview: it.preview || "" };
      pl.push(n); plKeys[key(n)] = 1;
      if (plMode) {
        var idx = pl.length - 1;
        if (plMix) plOrder.splice(plPos + 1 + Math.floor(Math.random() * (plOrder.length - plPos)), 0, idx); else plOrder.push(idx);
      }
    }
    b.disabled = false; setAdd(b, true);
    status("Masuk playlist (" + pl.length + " lagu). Lagu disiapkan di latar belakang.");
    if (tg && tg.HapticFeedback) tg.HapticFeedback.impactOccurred("light");
    drawPl(); toast("Ditambahkan ke Playlist Kamu", true);
  }).catch(function (e) { b.disabled = false; status("Gagal: " + e.message, false); });
}
function delPl(i) {
  postJ("api/pldel", { i: i }).then(function () {
    pl.splice(i, 1); rebuildKeys();
    if (plMode) {
      var p = plOrder.indexOf(i);
      plOrder = plOrder.filter(function (x) { return x !== i; }).map(function (x) { return x > i ? x - 1 : x; });
      if (p !== -1 && p <= plPos) plPos--;
    }
    drawPl(); drawSearch(); status("Dihapus dari playlist (" + pl.length + " lagu)."); toast("Dihapus dari Playlist Kamu", true);
  }).catch(function (e) { status("Gagal: " + e.message, false); });
}
function clearPl() {
  if (!pl.length) return;
  var go = function () {
    postJ("api/plclear", {}).then(function () {
      pl = []; rebuildKeys(); plMode = false; plPage = 1; updNav(); drawPl(); drawSearch(); status("Playlist dikosongkan.");
    }).catch(function (e) { status("Gagal: " + e.message, false); });
  };
  var msg = "Kosongkan seluruh playlist (" + pl.length + " lagu)?";
  if (tg && tg.showConfirm) tg.showConfirm(msg, function (ok) { if (ok) go(); }); else if (window.confirm(msg)) go();
}
function buildOrder(first) {
  plOrder = pl.map(function (_, i) { return i; });
  if (plMix) {
    for (var i = plOrder.length - 1; i > 0; i--) { var j = Math.floor(Math.random() * (i + 1)); var t = plOrder[i]; plOrder[i] = plOrder[j]; plOrder[j] = t; }
    if (first != null) { plOrder.splice(plOrder.indexOf(first), 1); plOrder.unshift(first); }
    plPos = 0;
  } else plPos = first != null ? first : 0;
}
function startPl(mix, first) {
  if (!pl.length) { status("Playlist masih kosong. Ketuk + di hasil pencarian.", false); return; }
  plMix = mix; plMode = true; plFails = 0; buildOrder(first); playAt();
}
function playAt() {
  var it = pl[plOrder[plPos]]; if (!it) return;
  plMode = true; play(it, true); updNav(); drawPl();
}
var lastNav = 0;
function navOk() { var n = Date.now(); if (n - lastNav < 450) return false; lastNav = n; return true; }
function nextPl() {
  if (!plMode || !navOk()) return;
  var np = plPos + 1;
  if (np >= plOrder.length) {
    if (plLoop && pl.length) { buildOrder(null); np = 0; }
    else { plMode = false; updNav(); drawPl(); status("Playlist selesai."); return; }
  }
  plPos = np; playAt();
}
function prevPl() {
  if (!plMode || !navOk()) return;
  if (au.currentTime > 5) { au.currentTime = 0; return; }
  plPos = Math.max(0, plPos - 1); playAt();
}
var au2 = new Audio(); au2.preload = "auto";
function prefetchNext() {
  var a = queue[0] || (plMode ? pl[plOrder[plPos + 1]] : null), b = queue[1] || (plMode ? pl[plOrder[plPos + (queue[0] ? 1 : 2)]] : null);
  function one(it, buf) {
    if (!it) return Promise.resolve();
    var p = it.stream ? Promise.resolve({ url: it.stream }) : resolveIt(it, 4, true);
    return p.then(function (j) { it.stream = j.url; if (buf) { au2.src = base + j.url; } }).catch(function () {});
  }
  one(a, true); one(b, false);   // paralel: lagu yang sudah siap tidak menunggu lagu lain yang masih diunduh
}
function plRow(it, i) {
  var d = mk("div", "pr"); d.setAttribute("data-i", i);
  var n = mk("div", "pn"); n.innerHTML = '<span class="pnn">' + (i + 1) + '</span><svg class="pp" viewBox="0 0 24 24"><path d="M8 4.7c0-.8.9-1.3 1.6-.9l10 6.3c.6.4.6 1.4 0 1.8l-10 6.3c-.7.4-1.6-.1-1.6-.9z"/></svg><span class="eq"><i></i><i></i><i></i></span>';
  var tb = mk("div", "ptb"); tb.appendChild(cvImg(it, "pcv"));
  var tx = mk("div", "tx"); tx.appendChild(mk("div", "t", it.title)); tx.appendChild(mk("div", "a", it.artist)); tb.appendChild(tx);
  var du = mk("div", "pd", it.ms ? fmt(it.ms / 1000) : "");
  var mo = mk("button", "hmore"); mo.innerHTML = DOTS; mo.setAttribute("aria-label", "Opsi lainnya");
  mo.addEventListener("click", function (e) { e.stopPropagation(); openMenu(it, e); });
  d.appendChild(n); d.appendChild(tb); d.appendChild(du); d.appendChild(mo);
  d.addEventListener("click", function () { startPl(plMix, i); });
  ctx(d, it);
  return d;
}
function markPl() {
  var r = document.querySelector("#pllist .pr.on"), o = document.querySelector("#pllist .pr.pg");
  if (o && o !== r) o.classList.remove("pg");
  if (r) r.classList.toggle("pg", !!(ready && !au.paused));
  setIc($("pl-o"), !!(plMode && ready && !au.paused));
  var ar = document.querySelectorAll("#arbody .pr");   // baris lagu di halaman artis
  for (var i = 0; i < ar.length; i++) { var on = !!cur && ar[i]._k === key(cur); ar[i].classList.toggle("on", on); ar[i].classList.toggle("pg", on && !!(ready && !au.paused)); }
}
function drawPlHead() {
  var cov = $("plcov"); cov.textContent = "";
  if (pl.length >= 4) { cov.className = "plcov mos"; pl.slice(0, 4).forEach(function (it) { cov.appendChild(cvImg(it, "")); }); }
  else if (pl.length) { cov.className = "plcov"; cov.appendChild(cvImg(pl[0], "")); }
  else { cov.className = "plcov hrt"; cov.innerHTML = HEART; }
  var tot = 0; pl.forEach(function (x) { tot += (x.ms || 0); });
  var m = (ME ? ME + " \u00b7 " : "") + pl.length + " lagu";
  if (tot > 0) { var mn = Math.round(tot / 60000); m += ", " + (mn >= 60 ? Math.floor(mn / 60) + " j " + (mn % 60) + " mnt" : mn + " mnt"); }
  $("plmeta").textContent = m;
  if (pl.length) coverColor(pl[0], function (c) { $("plh").style.setProperty("--plc", c); }); else $("plh").style.setProperty("--plc", "#4a3a78");
}
function drawPl() {
  var box = $("pllist");
  var sig = pl.map(key).join("~");
  if (box._sig !== sig) {
    box._sig = sig; box.textContent = "";
    if (!pl.length) {
      var e = document.createElement("div"); e.className = "empty"; e.textContent = "Playlist masih kosong. Cari lagu, lalu ketuk + untuk menambahkan. Jumlah lagu tanpa batas."; box.appendChild(e);
    } else {
      pl.forEach(function (it, i) { box.appendChild(plRow(it, i)); });
    }
    drawPlHead();
  }
  var cp = plMode ? plOrder[plPos] : -1, rs = box.children;
  for (var q = 0; q < rs.length; q++) { var ri = rs[q].getAttribute("data-i"); if (ri !== null) rs[q].className = "pr" + (+ri === cp ? " on" : ""); }
  markPl();
  $("plpgr").className = "pager hide";
  $("pl-l").className = "pab" + repCls(); $("pl-r").className = "pab" + (plMix ? " on" : "");
  setIc($("pl-o"), plMode && ready && !au.paused);
  $("t-pl").textContent = "Playlist" + (pl.length ? " (" + pl.length + ")" : "");
  syncNp();
  drawSide();
  if (curTab === "home") drawHome();
}
$("plprev").addEventListener("click", function () { if (plPage > 1) { plPage--; drawPl(); } });
$("plnext").addEventListener("click", function () { plPage++; drawPl(); });
$("pl-o").addEventListener("click", function () { if (plMode && cur) $("pbtn").click(); else startPl(plMix, null); });
$("pl-r").addEventListener("click", function () { toggleShuf(); });
$("pl-l").addEventListener("click", function () { cycleRep(); });
$("pl-c").addEventListener("click", clearPl);
$("pprev").addEventListener("click", prevPl);
$("pnext").addEventListener("click", function () { skipNext(); });
// ---------------------------------------------------------------- kartu lagu (Now Playing) seperti Spotify: ketuk pemutar kecil untuk membukanya
var DEFACC = "rgb(90,31,58)", npSeq = 0, lyr = null, lyIdx = -2, lyOpen = false, npVisible = false;
function enc(x) { return encodeURIComponent(x); }
function setAcc(c) { $("np").style.setProperty("--acc", c); }
function npColor(url, my) {   // warna kartu diambil dari rata-rata warna cover (kalau server gambar mengizinkan), kalau tidak pakai warna bawaan
  var im = new Image(); im.crossOrigin = "anonymous";
  im.onload = function () {
    if (my !== npSeq) return;
    try {
      var c = document.createElement("canvas"); c.width = 8; c.height = 8;
      var x = c.getContext("2d"); x.drawImage(im, 0, 0, 8, 8);
      var d = x.getImageData(0, 0, 8, 8).data, r = 0, g = 0, b = 0, n = 0;
      for (var i = 0; i < d.length; i += 4) { r += d[i]; g += d[i + 1]; b += d[i + 2]; n++; }
      var k = 0.55;
      setAcc("rgb(" + Math.round(r / n * k) + "," + Math.round(g / n * k) + "," + Math.round(b / n * k) + ")");
    } catch (e) { setAcc(DEFACC); }
  };
  im.onerror = function () { if (my === npSeq) setAcc(DEFACC); };
  im.src = url;
}
function npTrack(it) {
  vStop();
  var my = ++npSeq, cv = it.cover || "";
  $("npt").textContent = it.title; $("npa").textContent = it.artist; $("npar").textContent = (it.artist || "").split(",")[0];
  $("nphero").style.backgroundImage = cv ? "url('" + cv.split("'").join("%27") + "')" : "none";
  paintBg(cv);
  $("npai").src = cv || BLANK;
  setAcc(DEFACC); if (cv) npColor(cv, my);
  lyr = null; lyIdx = -2; renderLy();
  if (npVisible) loadLy(it, my);
  syncNp(); npBtn(); npTime();
}
function loadLy(it, my) {
  if (it.lyr !== undefined) { lyr = it.lyr; renderLy(); return; }
  api("api/lyrics?title=" + enc(it.title) + "&artist=" + enc(it.artist) + "&ms=" + (it.ms || 0)).then(function (j) {
    it.lyr = (j && j.lines && j.lines.length) ? j : null;
    if (my === npSeq) { lyr = it.lyr; renderLy(); }
  }).catch(function () {});
}
function renderLy() {
  var card = $("nplyr"), box = $("nplines"); box.textContent = ""; box.style.height = "";
  if (!lyr) { card.className = "npcard hide"; if (lfOpen) lfRender(); return; }
  card.className = "npcard" + (lyOpen ? " open" : "");
  var inn = document.createElement("div"); inn.className = "nli"; inn.style.transition = "none"; box.appendChild(inn);
  lyr.lines.forEach(function (ln) { var d = document.createElement("div"); d.className = "ll"; d.textContent = ln[1] || "\u266A"; inn.appendChild(d); });
  lyIdx = -2; paintLy(true);
  void inn.offsetHeight; inn.style.transition = "";
  if (lfOpen) lfRender();   // posisi awal tanpa animasi, perpindahan berikutnya halus
}
var scAnim = 0;
function easeIO(t) { return t < .5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2; }
function smoothScroll(box, to, instant) {   // gulir halus dengan kurva ease-in-out (tanpa bergantung pada scroll-behavior bawaan)
  cancelAnimationFrame(scAnim);
  to = Math.max(0, Math.min(to, box.scrollHeight - box.clientHeight));
  if (instant) { box.scrollTop = to; return; }
  var from = box.scrollTop, d = to - from, t0 = performance.now(), dur = 650;
  if (Math.abs(d) < 2) return;
  (function step(now) {
    var k = Math.min(1, (now - t0) / dur);
    box.scrollTop = from + d * easeIO(k);
    if (k < 1) scAnim = requestAnimationFrame(step);
  })(t0);
}
var LY_LEAD = 0.5;   // baris berikutnya mulai bergerak sedikit sebelum dinyanyikan, seperti Spotify
function paintLy(force) {
  if (!lyr) return;
  var ct = au.currentTime || 0, idx = -1, L = lyr.lines;
  if (lyr.synced) for (var i = 0; i < L.length; i++) { if (L[i][0] <= ct + LY_LEAD) idx = i; else break; }
  if (!force && idx === lyIdx) return;
  lyIdx = idx;
  if (lfOpen) lfPaint(force);
  var box = $("nplines"), inn = box.firstChild; if (!inn) return;
  var els = inn.children, a = lyr.synced ? Math.max(idx, 0) : 0, sy = !!lyr.synced;
  for (var k = 0; k < els.length; k++) {
    var e = els[k], d = Math.abs(k - a);
    e.className = "ll" + (sy && k === idx ? " cur" : "") + (lyOpen ? "" : (k < a ? " past" : (k === a || k === a + 1 ? "" : " far")));
    if (lyOpen && sy) {   // tampilan penuh: makin jauh dari baris aktif makin pudar, kecil, dan sedikit buram
      e.style.opacity = d === 0 ? (idx < 0 ? .6 : 1) : d === 1 ? .62 : d === 2 ? .46 : d === 3 ? .34 : .24;
      e.style.transform = "scale(" + (k === idx ? 1 : .95) + ")";
      e.style.filter = d <= 1 ? "none" : "blur(" + Math.min(1.6, (d - 1) * .45).toFixed(2) + "px)";
    } else { e.style.opacity = ""; e.style.transform = ""; e.style.filter = ""; }
  }
  if (lyOpen) {   // kartu terbuka: baris aktif digulir ke sepertiga atas, semua baris terlihat
    box.style.height = ""; inn.style.transform = "";
    if (idx >= 0) smoothScroll(box, els[idx].offsetTop - box.clientHeight * 0.35, force);
  } else if (els[a]) {   // pratinjau: jendela 2 baris yang bergeser naik tiap pergantian baris
    var f = els[a], g = els[a + 1] || f;
    box.style.height = (g.offsetTop + g.offsetHeight - f.offsetTop) + "px";
    inn.style.transform = "translateY(" + (-f.offsetTop) + "px)";
  }
}
function npTime() {
  if (!npVisible || seeking) return;
  var d = au.duration, ok = ready && d && isFinite(d);
  $("npbar").style.width = ok ? (au.currentTime / d * 100) + "%" : "0";
  $("npcur").textContent = ok ? fmt(au.currentTime) : "0:00";
  $("npdur").textContent = ok ? fmt(d) : "Memuat...";
  paintLy(false);
}
function npBtn() { setIc($("npplay"), ready && !au.paused); setIc($("lfplay"), ready && !au.paused); }
function syncNp() {
  var b = $("npadd"), on = !!cur && inPl(cur);
  setAdd(b, on);
  b.setAttribute("aria-label", on ? "Hapus dari playlist" : "Tambah ke playlist");
  $("npprev").disabled = !plMode; $("npnext").disabled = !(plMode || queue.length);
  $("nploop").className = "npb" + repCls(); $("npshuf").className = "npb" + (plMix ? " on" : "");
  dSync();
}
var vEl = $("npvid"), vSeq = 0, vTimer = null, vFor = "", vTry = 0;
var cvEl = $("npcv"), cvx = cvEl.getContext("2d"), bgEl = $("npbg"), bgx = bgEl.getContext("2d"), vRaf = 0, vLast = 0;
function vidOf(it) { var m = /[?&]v=([A-Za-z0-9_-]{11})/.exec((it && it.stream) || ""); return m ? m[1] : ""; }
function vStop() {
  clearTimeout(vTimer); vSeq++; vFor = ""; vTry = 0;
  cancelAnimationFrame(vRaf); vRaf = 0;
  cvEl.className = "npvid"; $("nphero").classList.remove("hv");
  try { vEl.pause(); } catch (e) {}
  if (vEl.getAttribute("src")) { vEl.removeAttribute("src"); try { vEl.load(); } catch (e) {} }
}
function vPlayState() {
  if (!vEl.getAttribute("src")) return;
  if (au.paused || !ready) { try { vEl.pause(); } catch (e) {} vStartDraw(); return; }
  var p = vEl.play(); if (p && p.catch) p.catch(function () {});
  vStartDraw();
}
function vDrift(force) {   // sinkron video ke audio: selisih kecil dikejar lewat kecepatan putar, loncat posisi hanya kalau selisih besar
  if (!vEl.getAttribute("src") || vEl.readyState < 2 || !ready) return;
  var ct = au.currentTime || 0, d = ct - vEl.currentTime, ad = Math.abs(d);
  if (force || ad > 2.5) { try { vEl.currentTime = ct; vEl.playbackRate = 1; } catch (e) {} return; }
  if (ad > 0.3) vEl.playbackRate = d > 0 ? 1.1 : 0.9;
  else if (ad < 0.12 && vEl.playbackRate !== 1) vEl.playbackRate = 1;
}
// video digambar ke <canvas> biasa (bukan elemen <video> yang tampil), supaya tidak hilang / hitam saat halaman digulir di WebView Android
function vStartDraw() { if (!vRaf) vRaf = requestAnimationFrame(vDraw); }
function vDraw(ts) {
  vRaf = 0;
  if (!npVisible || !vEl.getAttribute("src") || vEl.readyState < 2) return;
  if (!ts || ts - vLast >= 30) {   // sekitar 30 fps cukup untuk klip lirik dan lebih hemat baterai
    vLast = ts || 0;
    var dpr = Math.min(window.devicePixelRatio || 1, 2), W = Math.round(cvEl.clientWidth * dpr), H = Math.round(cvEl.clientHeight * dpr);
    var vw = vEl.videoWidth, vh = vEl.videoHeight;
    if (W && H && vw && vh) {
      if (cvEl.width !== W || cvEl.height !== H) { cvEl.width = W; cvEl.height = H; }
      var sc = Math.min(W / vw, H / vh), dw = vw * sc, dh = vh * sc;
      cvx.clearRect(0, 0, W, H); cvx.drawImage(vEl, (W - dw) / 2, (H - dh) / 2, dw, dh);
    }
  }
  if (!vEl.paused) vRaf = requestAnimationFrame(vDraw);
}
vEl.addEventListener("seeked", vStartDraw);
function paintBg(url) {   // latar kabur dari cover: gambar kecil 16x16 diregangkan, jauh lebih ringan daripada filter blur
  bgEl._u = url || ""; bgx.clearRect(0, 0, 16, 16);
  if (!url) return;
  var im = new Image();
  im.onload = function () { if (bgEl._u !== url) return; try { bgx.drawImage(im, 0, 0, 16, 16); bgx.fillStyle = "rgba(0,0,0,.5)"; bgx.fillRect(0, 0, 16, 16); } catch (e) {} };
  im.src = url;
}
function vSync() {   // minta server menyiapkan video klip; sebelum siap, yang tampil tetap foto cover
  if (!npVisible || !cur || !cur.stream) return;
  var id = vidOf(cur); if (!id || id === vFor) return;
  vStop(); vFor = id;
  var my = vSeq;
  function poll() {
    api("api/vinfo?v=" + id).then(function (r) {
      if (my !== vSeq) return;
      if (r && r.ready && r.url) {
        vEl.muted = true; vEl.loop = false;
        vEl.onloadeddata = function () { if (my !== vSeq) return; cvEl.className = "npvid on"; $("nphero").classList.add("hv"); vDrift(true); vPlayState(); vStartDraw(); };
        vEl.onerror = function () { if (my === vSeq) { cvEl.className = "npvid"; $("nphero").classList.remove("hv"); } };
        vEl.src = base + r.url;
      } else if (r && !r.off && ++vTry < 90) {
        vTimer = setTimeout(poll, 2500);
      }
    }).catch(function () { if (my === vSeq && ++vTry < 90) vTimer = setTimeout(poll, 4000); });
  }
  poll();
}
au.addEventListener("play", vPlayState); au.addEventListener("pause", vPlayState);
au.addEventListener("seeked", function () { vDrift(true); });
au.addEventListener("timeupdate", function () { vDrift(false); });
function openNp() {
  if (!cur) return;
  npVisible = true; $("np").scrollTop = 0; $("np").className = "np"; document.body.style.overflow = "hidden"; deskClosed = false; setRp(); try { if (tg && tg.disableVerticalSwipes) tg.disableVerticalSwipes(); } catch (e) {}
  try { if (tg && tg.BackButton) { tg.BackButton.onClick(closeNp); tg.BackButton.show(); } } catch (e) {}
  npTrack(cur); vSync();
}
function closeNp() {
  vStop();
  npVisible = false; $("np").className = "np closed"; document.body.style.overflow = ""; deskClosed = true; closeQ(); closeLy(); setRp(); try { if (tg && tg.enableVerticalSwipes) tg.enableVerticalSwipes(); } catch (e) {}
  try { if (tg && tg.BackButton) { tg.BackButton.offClick(closeNp); tg.BackButton.hide(); } } catch (e) {}
}
$("pl").addEventListener("click", function (e) {
  var t = e.target;
  if (t.closest && (t.closest("button") || t.closest("#pbarw"))) return;
  openNp();
});
$("npx").addEventListener("click", closeNp);
$("npplay").addEventListener("click", function () { $("pbtn").click(); });
$("npprev").addEventListener("click", prevPl);
$("npnext").addEventListener("click", function () { skipNext(); });
$("nploop").addEventListener("click", function () { $("pl-l").click(); });
$("npbarw").addEventListener("click", function (e) {
  if (!ready || !au.duration || !isFinite(au.duration)) return;
  var r = this.getBoundingClientRect();
  au.currentTime = Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)) * au.duration;
});
$("npadd").addEventListener("click", function () {
  if (!cur) return;
  if (inPl(cur)) {
    var k = key(cur);
    for (var i = 0; i < pl.length; i++) if (key(pl[i]) === k) { delPl(i); break; }
  } else addPl(cur, this);
});
$("nplyr").addEventListener("click", function () { lyOpen = !lyOpen; this.className = "npcard" + (lyOpen ? " open" : ""); paintLy(true); });
$("npshare").addEventListener("click", function () {
  if (!cur) return;
  var txt = cur.title + " - " + cur.artist;
  var link = "https://www.youtube.com/results?search_query=" + enc(txt);
  var u = "https://t.me/share/url?url=" + enc(link) + "&text=" + enc("Dengerin lagu ini: " + txt);
  try { if (tg && tg.openTelegramLink) { tg.openTelegramLink(u); return; } } catch (e) {}
  if (navigator.share) navigator.share({ title: txt, url: link }).catch(function () {}); else window.open(u, "_blank");
});
$("npmore").addEventListener("click", function () {
  if (!cur) return;
  var a = (cur.artist || "").split(",")[0].trim(); if (!a) return;
  openArtist(a);
});

setAdd($("npadd"), false);

// ---------------------------------------------------------------- Beranda ala Spotify
var recentAll = [], homeChip = "all";
var ME = (tg && tg.initDataUnsafe && tg.initDataUnsafe.user) ? String(tg.initDataUnsafe.user.first_name || tg.initDataUnsafe.user.username || "") : "";
var HEART = '<svg viewBox="0 0 24 24" fill="#fff"><path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/></svg>';
var GLOBE = '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3.2 3.4 3.2 14.6 0 18M12 3c-3.2 3.4-3.2 14.6 0 18"/></svg>';
var DOTS = '<svg viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="5" r="1.8"/><circle cx="12" cy="12" r="1.8"/><circle cx="12" cy="19" r="1.8"/></svg>';
function mk(tag, cls, txt) { var e = document.createElement(tag); if (cls) e.className = cls; if (txt != null) e.textContent = txt; return e; }
function cvImg(it, cls) { var im = mk("img", cls); im.alt = ""; im.loading = "lazy"; im.src = it.cover || BLANK; return im; }
function uk(list) { var sn = {}, o = []; list.forEach(function (x) { var k = key(x); if (!sn[k]) { sn[k] = 1; o.push(x); } }); return o; }
function homePlay(it) { play(it); }
function tile(name, art, fn, it) {
  var d = mk("div", "ht"); d.appendChild(art); d.appendChild(mk("span", "", name));
  if (it) {
    var pb = mk("div", "hpb"); pb.innerHTML = IC_PLAY; d.appendChild(pb); ctx(d, it);
    d.addEventListener("mouseenter", function () { if (isDesk()) coverColor(it, setHg); });
    d.addEventListener("mouseleave", function () { setHg(""); });
  }
  d.addEventListener("click", fn); return d;
}
function hcw(it) { var w = mk("div", "hcw"); w.appendChild(cvImg(it, "hcc")); var pb = mk("div", "hpb"); pb.innerHTML = IC_PLAY; w.appendChild(pb); return w; }
function artBox(cls, svg) { var d = mk("div", "hart " + cls); d.innerHTML = svg; return d; }
function togglePl(it, b) {
  if (inPl(it)) { var k = key(it); for (var i = 0; i < pl.length; i++) if (key(pl[i]) === k) { delPl(i); break; } }
  else addPl(it, b || document.createElement("button"));
}
function rowMenu(it, e) { openMenu(it, e || { clientX: 20, clientY: 20 }); }
function homeRow(it) {
  var d = mk("div", "hr");
  d.appendChild(cvImg(it, "hrc"));
  var tx = mk("div", "tx"); tx.appendChild(mk("div", "hrt", it.title)); tx.appendChild(mk("div", "a", it.artist)); d.appendChild(tx);
  var ck = mk("button", "addb"); setAdd(ck, inPl(it)); ck.setAttribute("aria-label", "Playlist");
  ck.addEventListener("click", function (e) { e.stopPropagation(); togglePl(it, ck); });
  var mo = mk("button", "hmore"); mo.innerHTML = DOTS; mo.setAttribute("aria-label", "Opsi lainnya");
  mo.addEventListener("click", function (e) { e.stopPropagation(); rowMenu(it, e); });
  d.appendChild(ck); d.appendChild(mo);
  d.addEventListener("click", function () { homePlay(it); }); ctx(d, it);
  return d;
}
function setAvatar() {
  ["hav", "dav"].forEach(function (id) {
    var box = $(id); if (!box || box._done) return; box._done = 1;
    var u = tg && tg.initDataUnsafe && tg.initDataUnsafe.user;
    box.textContent = (ME.charAt(0) || "\u266A").toUpperCase();
    if (u && u.photo_url) {
      var im = new Image(); im.alt = "";
      im.onload = function () { box.textContent = ""; box.appendChild(im); };
      im.src = u.photo_url;
    }
  });
}
var allOn = {}, queue = [], qOpen = false, repOne = false, seeking = false, recentLoaded = false, lastVol = 1, lfOpen = false, lfUser = 0, curQuery = "", sfilter = "all", curArtist = "", lastMain = "home", sleepAt = 0, sleepEnd = false, sleepT = null, cf = 0, cfDone = false, uvol = 1, tail = null, tailT = null;
function secHead(id, t, sc) {
  var h = mk("div", "hhead"); h.appendChild(mk("h2", "hh", t));
  var b = mk("button", "hall", allOn[id] ? "Tampilkan lebih sedikit" : "Tampilkan semua");
  b.addEventListener("click", function () { allOn[id] = !allOn[id]; sc.classList.toggle("all", !!allOn[id]); b.textContent = allOn[id] ? "Tampilkan lebih sedikit" : "Tampilkan semua"; });
  h.appendChild(b); return h;
}
function artistsOf(list) {
  var m = {}, o = [];
  list.forEach(function (x) {
    var a = String(x.artist || "").split(",")[0].trim(); if (!a) return;
    var k = a.toLowerCase();
    if (!m[k]) { m[k] = { name: a, cover: x.cover, n: 0 }; o.push(m[k]); }
    m[k].n++; if (!m[k].cover) m[k].cover = x.cover;
  });
  o.sort(function (p, q) { return q.n - p.n; });
  return o;
}
function goArtist(name) { openArtist(name); }
function drawHome() {
  setAvatar();
  var box = $("hbody"), old = box.querySelector(".hscroll.rec"), keep = old ? old.scrollLeft : 0;
  box.textContent = "";
  if (homeChip === "pod") { box.appendChild(mk("div", "empty", "Belum ada podcast di sini. Untuk sekarang khusus musik.")); return; }
  box.appendChild(mk("h1", "hgreet", greet()));
  var pool = seedShuf(uk(pl.concat(recentAll)));
  var g = mk("div", "hgrid");
  g.appendChild(tile("Playlist Kamu", artBox("g1", HEART), function () { showTab("pl"); }));
  g.appendChild(tile("Ruang Global", artBox("g2", GLOBE), function () { showTab("global"); }));
  pool.slice(0, 6).forEach(function (it) { g.appendChild(tile(it.title, cvImg(it, "hcv"), function () { homePlay(it); }, it)); });
  box.appendChild(g);
  var arts = artistsOf(pl.concat(recentAll)).slice(0, 14);
  if (arts.length) {
    var wrap = mk("div", "dsk"), sa = mk("div", "hscroll" + (allOn.art ? " all" : ""));
    arts.forEach(function (a) {
      var c = mk("div", "hc hca"); c.appendChild(hcw({ cover: a.cover })); c.appendChild(mk("div", "hn", a.name)); c.appendChild(mk("div", "hs", "Artis"));
      c.addEventListener("click", function () { goArtist(a.name); }); sa.appendChild(c);
    });
    wrap.appendChild(secHead("art", "Artis populer", sa)); wrap.appendChild(sa); box.appendChild(wrap);
  }
  if (!recentLoaded) {
    box.appendChild(mk("h2", "hh", "Baru saja didengar"));
    var ssk = mk("div", "hscroll");
    for (var q = 0; q < 6; q++) { var ck = mk("div", "hc"); ck.innerHTML = '<div class="skb hcc"></div><div class="skb skl"></div><div class="skb skl" style="width:55%"></div>'; ssk.appendChild(ck); }
    box.appendChild(ssk);
  }
  var rec = recentLoaded ? uk(recentAll).slice(0, 14) : [];
  if (rec.length) {
    var sc = mk("div", "hscroll rec" + (allOn.rec ? " all" : ""));
    rec.forEach(function (it) {
      var c = mk("div", "hc");
      c.appendChild(hcw(it));
      c.appendChild(mk("div", "hs", (it.who || "Seseorang") + " \u00b7 " + ago(it.ts)));
      c.appendChild(mk("div", "hn", it.title));
      c.appendChild(mk("div", "hs", it.artist));
      c.addEventListener("click", function () { homePlay(it); }); ctx(c, it);
      sc.appendChild(c);
    });
    box.appendChild(secHead("rec", "Baru saja didengar", sc)); box.appendChild(sc); sc.scrollLeft = keep;
  }
  var mine = recentAll.filter(function (x) { return ME && String(x.who || "").toLowerCase() === ME.toLowerCase(); });
  var often = uk(mine.length ? mine : pl).slice(0, 8);
  if (often.length) {
    box.appendChild(mk("h2", "hh", "Sering kamu putar baru-baru ini"));
    var rows = mk("div", "hrows");
    often.forEach(function (it) { rows.appendChild(homeRow(it)); });
    box.appendChild(rows);
  }
  if (!pool.length) box.appendChild(mk("div", "empty", "Belum ada lagu. Buka tab Cari untuk mulai mencari lagu."));
}
function loadHome() {
  return api("api/recent").then(function (j) { recentAll = j.items || []; recentLoaded = true; if (curTab === "home") drawHome(); }).catch(function () { recentLoaded = true; if (curTab === "home") drawHome(); });
}
var chips = document.querySelectorAll(".chip");
for (var ci = 0; ci < chips.length; ci++) chips[ci].addEventListener("click", function () {
  homeChip = this.getAttribute("data-c");
  for (var k = 0; k < chips.length; k++) chips[k].className = "chip" + (chips[k] === this ? " on" : "");
  drawHome();
});
var navBtns = document.querySelectorAll("#bnav button");
for (var ni = 0; ni < navBtns.length; ni++) navBtns[ni].addEventListener("click", function () { showTab(this.getAttribute("data-t")); });

// ---------------------------------------------------------------- layout desktop (laptop / PC)
var deskClosed = false;
var LIBI = '<svg viewBox="0 0 24 24"><path d="M5 4v16M10 4v16M15 5.5l4.5 14.5"/></svg>';
var PLUSI = '<svg viewBox="0 0 24 24"><path d="M12 5v14M5 12h14"/></svg>';
function isDesk() { return !!(window.matchMedia && window.matchMedia("(min-width:1000px)").matches); }
function setRp() { document.body.classList.toggle("rp", isDesk() && (npVisible || qOpen)); }
function dSync() {
  if (!$("dbar")) return;
  var it = cur;
  $("dcv").src = it ? (it.cover || BLANK) : BLANK; $("dcv").style.visibility = it ? "visible" : "hidden";
  $("dt").textContent = it ? it.title : ""; $("da").textContent = it ? it.artist : "";
  $("dadd").style.visibility = it ? "visible" : "hidden"; if (it) setAdd($("dadd"), inPl(it));
  setIc($("dplay"), ready && !au.paused);
  $("dprev").disabled = !plMode; $("dnext").disabled = !(plMode || queue.length);
  $("dshuf").className = "dbtn" + (plMix ? " on" : "");
  $("dloop").className = "dbtn" + repCls();
  $("dpanel").className = "dbtn" + (npVisible ? " on" : "");
  $("dqueue").className = "dbtn" + (qOpen ? " on" : "");
}
function dTime() {
  if (seeking) return;
  var d = au.duration, ok = ready && d && isFinite(d);
  $("dbarfill").style.width = ok ? (au.currentTime / d * 100) + "%" : "0";
  $("dcur").textContent = ok ? fmt(au.currentTime) : "0:00";
  $("ddur").textContent = ok ? fmt(d) : "0:00";
}
function drawSide() {
  var sd = $("dside"); if (!sd) return; sd.textContent = "";
  var b1 = mk("button", "dsb"); b1.innerHTML = LIBI; b1.title = "Koleksi Kamu"; b1.addEventListener("click", function () { showTab("pl"); });
  var b2 = mk("button", "dsb"); b2.innerHTML = PLUSI; b2.title = "Cari & tambah lagu"; b2.addEventListener("click", function () { showTab("cari"); $("dq").focus(); });
  sd.appendChild(b1); sd.appendChild(b2);
  var h = mk("div", "dsh"); h.innerHTML = HEART; h.title = "Playlist Kamu"; h.addEventListener("click", function () { showTab("pl"); }); sd.appendChild(h);
  pl.slice(0, 40).forEach(function (it, i) {
    var im = cvImg(it, "dsc"); im.title = it.title + " - " + it.artist;
    im.addEventListener("click", function () { startPl(plMix, i); }); ctx(im, it); sd.appendChild(im);
  });
}
function togglePanel() {
  if (npVisible) { closeNp(); return; }
  if (!cur) return;
  deskClosed = false; npVisible = true; $("np").scrollTop = 0; $("np").className = "np"; setRp();
  npTrack(cur); vSync(); dSync();
}
$("dhome").addEventListener("click", function () { $("dq").value = ""; showTab("home"); });
$("dq").addEventListener("input", function () {
  if (curTab !== "cari") showTab("cari");
  $("q").value = this.value; $("q").dispatchEvent(new Event("input"));
});
$("dq").addEventListener("keydown", function (e) { if (e.key === "Enter") $("q").dispatchEvent(new KeyboardEvent("keydown", { key: "Enter" })); });
$("dplay").addEventListener("click", function () { $("pbtn").click(); });
$("dprev").addEventListener("click", prevPl);
$("dnext").addEventListener("click", function () { skipNext(); });
$("dshuf").addEventListener("click", function () { toggleShuf(); });
$("dloop").addEventListener("click", function () { $("pl-l").click(); });
$("dadd").addEventListener("click", function () { $("npadd").click(); });
$("dcv").addEventListener("click", togglePanel);
$("dpanel").addEventListener("click", togglePanel);
$("dbarw").addEventListener("click", function (e) {
  if (!ready || !au.duration || !isFinite(au.duration)) return;
  var r = this.getBoundingClientRect();
  au.currentTime = Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)) * au.duration;
});
$("dvol").addEventListener("input", function () { au.volume = this.value / 100; uvol = au.volume; volIc(); });
au.addEventListener("timeupdate", dTime); au.addEventListener("durationchange", dTime);
document.addEventListener("keydown", function (e) {
  var tn = (e.target && e.target.tagName) || "";
  if (e.code === "Space" && isDesk() && cur && !/INPUT|TEXTAREA|BUTTON/.test(tn)) { e.preventDefault(); $("pbtn").click(); }
});
var rzT = null;
window.addEventListener("resize", function () { setRp(); clearTimeout(rzT); rzT = setTimeout(function () { if (curTab === "pl") drawPl(); else if (curTab === "cari") drawSearch(); }, 120); });
dSync(); drawSide();

// ---------------------------------------------------------------- warna cover, menu lagu, antrean, acak/ulang, kontrol (ala Spotify)
var colCache = {};
function hashColor(str) { var h = 0; for (var i = 0; i < str.length; i++) h = (h * 31 + str.charCodeAt(i)) >>> 0; return "hsl(" + (h % 360) + ",36%,27%)"; }
function coverColor(it, cb, mul) {
  var url = it.cover || "", m = mul || .55, k = (url || key(it)) + "@" + m;
  if (colCache[k]) { cb(colCache[k]); return; }
  if (!url) { colCache[k] = hashColor(k); cb(colCache[k]); return; }
  var im = new Image(); im.crossOrigin = "anonymous";
  im.onload = function () {
    var c;
    try {
      var cv = document.createElement("canvas"); cv.width = 8; cv.height = 8;
      var x = cv.getContext("2d"); x.drawImage(im, 0, 0, 8, 8);
      var d = x.getImageData(0, 0, 8, 8).data, r = 0, g = 0, b = 0, n = 0;
      for (var i = 0; i < d.length; i += 4) { r += d[i]; g += d[i + 1]; b += d[i + 2]; n++; }
      c = "rgb(" + Math.round(r / n * m) + "," + Math.round(g / n * m) + "," + Math.round(b / n * m) + ")";
    } catch (e) { c = hashColor(k); }
    colCache[k] = c; cb(c);
  };
  im.onerror = function () { colCache[k] = hashColor(k); cb(colCache[k]); };
  im.src = url;
}
function setHg(c) { var m = $("dmain"); if (c) m.style.setProperty("--hg", c); else m.style.removeProperty("--hg"); }
function skel(box, n) {
  box.textContent = ""; box._sig = "skel";
  for (var i = 0; i < n; i++) { var r = mk("div", "sk"); r.innerHTML = '<div class="skb skc"></div><div class="skt"><div class="skb skl" style="width:62%"></div><div class="skb skl" style="width:38%"></div></div>'; box.appendChild(r); }
}
function repCls() { return (plLoop || repOne ? " on" : "") + (repOne ? " one" : ""); }
function toggleShuf() {
  if (plMode) { var ci = plOrder[plPos]; plMix = !plMix; buildOrder(ci); } else plMix = !plMix;
  drawPl(); toast("Acak: " + (plMix ? "aktif" : "mati"), true);
}
function cycleRep() {
  if (!plLoop && !repOne) plLoop = true; else if (plLoop) { plLoop = false; repOne = true; } else repOne = false;
  if (ready && au.src && String(au.src).indexOf("data:") !== 0) au.loop = repOne;
  drawPl(); toast(repOne ? "Ulang satu lagu: aktif" : plLoop ? "Ulang playlist: aktif" : "Ulang: mati", true);
}
// ---- menu lagu (klik kanan di desktop / lembar bawah di HP)
function ctx(el, it) { el.addEventListener("contextmenu", function (e) { e.preventDefault(); openMenu(it, e); }); }
function shareIt(it) {
  var txt = it.title + " - " + it.artist, link = "https://www.youtube.com/results?search_query=" + enc(txt);
  var u = "https://t.me/share/url?url=" + enc(link) + "&text=" + enc("Dengerin lagu ini: " + txt);
  try { if (tg && tg.openTelegramLink) { tg.openTelegramLink(u); return; } } catch (e) {}
  if (navigator.share) navigator.share({ title: txt, url: link }).catch(function () {}); else window.open(u, "_blank");
}
function closeMenu() { $("cm").className = "cm hide"; $("cmb").className = "cmb hide"; }
function showMenu(acts, ev, head) {
  var m = $("cm"); m.textContent = "";
  if (head) m.appendChild(head);
  acts.forEach(function (a) { var b = mk("button", "cmi" + (a[2] ? " on" : ""), a[0]); b.addEventListener("click", function (e) { e.stopPropagation(); closeMenu(); a[1](); }); m.appendChild(b); });
  $("cmb").className = "cmb"; m.className = "cm";
  if (isDesk()) {
    var r = m.getBoundingClientRect(), x = (ev && ev.clientX) || 20, y = (ev && ev.clientY) || 20;
    m.style.left = Math.max(8, Math.min(x, innerWidth - r.width - 8)) + "px";
    m.style.top = Math.max(8, Math.min(y, innerHeight - r.height - 8)) + "px";
  } else { m.style.left = ""; m.style.top = ""; }
}
function openMenu(it, ev) {
  var on = inPl(it), art = primaryArtist(it);
  var h = mk("div", "cmh"); h.appendChild(mk("img", "cmc")); h.firstChild.src = it.cover || BLANK;
  var ht = mk("div", "tx"); ht.appendChild(mk("div", "t", it.title)); ht.appendChild(mk("div", "a", it.artist)); h.appendChild(ht);
  var acts = [
    ["Putar", function () { play(it); }],
    ["Putar berikutnya", function () { playNextQ(it); }],
    ["Tambah ke antrean", function () { addQueue(it); }],
    [on ? "Hapus dari Playlist Kamu" : "Tambah ke Playlist Kamu", function () { togglePl(it); }]
  ];
  if (art) acts.push(["Buka artis", function () { openArtist(art); }]);
  acts.push(["Bagikan", function () { shareIt(it); }]);
  showMenu(acts, ev, h);
}
$("cmb").addEventListener("click", closeMenu);
$("cmb").addEventListener("contextmenu", function (e) { e.preventDefault(); closeMenu(); });
// ---- antrean
function qChanged() { updNav(); syncNp(); if (qOpen) drawQueue(); }
function addQueue(it) { queue.push(it); toast("Ditambahkan ke antrean", true); qChanged(); }
function playNextQ(it) { queue.unshift(it); toast("Akan diputar berikutnya", true); qChanged(); }
function skipNext() {
  if (queue.length) { if (!navOk()) return; var it = queue.shift(); qChanged(); play(it, true); return; }
  nextPl();
}
function qRow(it, o) {
  var d = mk("div", "qr" + (o.now ? " now" : ""));
  d.appendChild(cvImg(it, "qc"));
  var tx = mk("div", "tx"); tx.appendChild(mk("div", "t", it.title)); tx.appendChild(mk("div", "a", it.artist)); d.appendChild(tx);
  if (o.qi != null) {
    var x = mk("button", "hmore"); x.innerHTML = IC_DEL; x.setAttribute("aria-label", "Hapus dari antrean");
    x.addEventListener("click", function (e) { e.stopPropagation(); queue.splice(o.qi, 1); qChanged(); });
    d.appendChild(x);
  }
  d.addEventListener("click", function () {
    if (o.now) { $("pbtn").click(); return; }
    if (o.qi != null) { queue.splice(o.qi, 1); qChanged(); play(it, true); return; }
    if (o.pp != null) { plPos = o.pp; playAt(); }
  });
  ctx(d, it);
  return d;
}
function drawQueue() {
  var b = $("qb"); b.textContent = "";
  if (cur) { b.appendChild(mk("div", "qs", "Sekarang diputar")); b.appendChild(qRow(cur, { now: true })); }
  if (queue.length) {
    var h = mk("div", "qs"); h.appendChild(mk("span", "", "Berikutnya dalam antrean"));
    var cl = mk("button", "", "Kosongkan"); cl.addEventListener("click", function () { queue = []; qChanged(); }); h.appendChild(cl); b.appendChild(h);
    queue.forEach(function (it, i) { b.appendChild(qRow(it, { qi: i })); });
  }
  var up = plMode ? plOrder.slice(plPos + 1) : [];
  if (up.length) {
    b.appendChild(mk("div", "qs", "Berikutnya dari Playlist Kamu"));
    up.slice(0, 30).forEach(function (pi, k) { if (pl[pi]) b.appendChild(qRow(pl[pi], { pp: plPos + 1 + k })); });
  }
  if (!cur) b.appendChild(mk("div", "empty", "Belum ada lagu yang diputar."));
  else if (!queue.length && !up.length) b.appendChild(mk("div", "empty", "Belum ada lagu berikutnya. Buka menu \u22EE pada lagu, lalu pilih Tambah ke antrean."));
}
function openQ() { qOpen = true; $("qp").className = "qp"; drawQueue(); setRp(); dSync(); }
function closeQ() { if (!qOpen) return; qOpen = false; $("qp").className = "qp closed"; setRp(); dSync(); }
function toggleQ() { if (qOpen) closeQ(); else openQ(); }
$("qx").addEventListener("click", closeQ);
$("dqueue").addEventListener("click", toggleQ);
$("npq").addEventListener("click", toggleQ);
$("npshuf").addEventListener("click", toggleShuf);
// ---- volume: bisukan
var VOLI = '<svg class="lp" viewBox="0 0 24 24"><path d="M4 9v6h4l5 4V5L8 9z"/><path d="M16.5 9a4 4 0 010 6"/></svg>';
var MUTI = '<svg class="lp" viewBox="0 0 24 24"><path d="M4 9v6h4l5 4V5L8 9z"/><path d="M17 9l5 6M22 9l-5 6"/></svg>';
function volIc() { $("dmute").innerHTML = au.volume === 0 ? MUTI : VOLI; }
$("dmute").addEventListener("click", function () {
  if (au.volume > 0) { lastVol = au.volume; au.volume = 0; $("dvol").value = 0; } else { au.volume = lastVol || 1; $("dvol").value = Math.round(au.volume * 100); }
  uvol = au.volume; volIc();
});
volIc();
// ---- bar progres bisa diseret + tooltip waktu
function dragBar(w, fillId, curId) {
  var fill = $(fillId), tm = curId ? $(curId) : null;
  function upd(e) {
    var r = w.getBoundingClientRect(), k = Math.min(1, Math.max(0, (e.clientX - r.left) / r.width));
    fill.style.width = (k * 100) + "%"; if (tm) tm.textContent = fmt(k * au.duration); w._r = k;
  }
  w.addEventListener("pointerdown", function (e) {
    if (!ready || !au.duration || !isFinite(au.duration)) return;
    seeking = true; w._drag = true; w.classList.add("drag");
    try { w.setPointerCapture(e.pointerId); } catch (x) {}
    upd(e);
  });
  w.addEventListener("pointermove", function (e) { if (w._drag) upd(e); });
  function end(ok) {
    if (!w._drag) return; w._drag = false; seeking = false; w.classList.remove("drag");
    if (ok && w._r != null && au.duration) au.currentTime = w._r * au.duration;
  }
  w.addEventListener("pointerup", function () { end(true); });
  w.addEventListener("pointercancel", function () { end(false); });
}
dragBar($("dbarw"), "dbarfill", "dcur"); dragBar($("npbarw"), "npbar", "npcur"); dragBar($("pbarw"), "pbar", null);
$("dbarw").addEventListener("mousemove", function (e) {
  if (!ready || !au.duration || !isFinite(au.duration)) return;
  var r = this.getBoundingClientRect(), k = Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)), t = $("dtip");
  t.textContent = fmt(k * au.duration); t.style.left = (k * 100) + "%"; t.className = "btip";
});
$("dbarw").addEventListener("mouseleave", function () { $("dtip").className = "btip hide"; });
// ---- tombol media di layar kunci / notifikasi / keyboard (Media Session)
function msSet(it) {
  try { if (!navigator.mediaSession || !window.MediaMetadata) return;
    navigator.mediaSession.metadata = new MediaMetadata({ title: it.title, artist: it.artist || "", album: "Spotify", artwork: it.cover ? [{ src: it.cover, sizes: "512x512" }] : [] });
  } catch (e) {}
}
function msPos() {
  try { if (!navigator.mediaSession || !navigator.mediaSession.setPositionState || !ready || !au.duration || !isFinite(au.duration)) return;
    navigator.mediaSession.setPositionState({ duration: au.duration, playbackRate: 1, position: Math.min(au.currentTime, au.duration) });
  } catch (e) {}
}
["loadedmetadata", "play", "pause", "seeked", "durationchange"].forEach(function (n) { au.addEventListener(n, msPos); });
(function () {
  if (!navigator.mediaSession) return;
  function h(a, f) { try { navigator.mediaSession.setActionHandler(a, f); } catch (e) {} }
  h("play", function () { if (cur && ready) au.play().catch(function () {}); });
  h("pause", function () { au.pause(); });
  h("previoustrack", function () { if (plMode) prevPl(); else au.currentTime = 0; });
  h("nexttrack", function () { skipNext(); });
  h("seekto", function (d) { if (ready && d && d.seekTime != null) au.currentTime = d.seekTime; });
  h("seekbackward", function (d) { au.currentTime = Math.max(0, au.currentTime - ((d && d.seekOffset) || 10)); });
  h("seekforward", function (d) { au.currentTime = Math.min(au.duration || 1e9, au.currentTime + ((d && d.seekOffset) || 10)); });
})();
// ---- pintasan keyboard
document.addEventListener("keydown", function (e) {
  var t = e.target || {}, tn = t.tagName || "";
  var typing = /TEXTAREA|SELECT/.test(tn) || (tn === "INPUT" && t.type !== "range");
  if ((e.ctrlKey || e.metaKey) && (e.key === "k" || e.key === "K")) { e.preventDefault(); if (isDesk()) $("dq").focus(); else { showTab("cari"); $("q").focus(); } return; }
  if (e.key === "Escape") { closeMenu(); if (lfOpen) closeLy(); else if (qOpen) closeQ(); else if (typing) t.blur(); return; }
  if (typing || e.ctrlKey || e.metaKey || e.altKey) return;
  if (e.key === "/") { e.preventDefault(); if (isDesk()) $("dq").focus(); else { showTab("cari"); $("q").focus(); } return; }
  if (!cur) return;
  if (e.code === "Space" && tn !== "BUTTON") { e.preventDefault(); $("pbtn").click(); }
  else if (e.key === "ArrowRight" && tn !== "INPUT" && ready) { e.preventDefault(); au.currentTime = Math.min(au.duration || 1e9, au.currentTime + 5); }
  else if (e.key === "ArrowLeft" && tn !== "INPUT" && ready) { e.preventDefault(); au.currentTime = Math.max(0, au.currentTime - 5); }
  else if (e.key === "n" || e.key === "N") skipNext();
  else if (e.key === "p" || e.key === "P") { if (plMode) prevPl(); else au.currentTime = 0; }
});
// ---- gestur di HP: geser bawah = tutup kartu, geser kiri/kanan = ganti lagu
(function () {
  var hero = $("nphero"), npEl = $("np"), sx = 0, sy = 0, dx = 0, dy = 0, ax = "", on = false;
  hero.addEventListener("touchstart", function (e) {
    if (isDesk() || e.touches.length !== 1) return;
    on = true; sx = e.touches[0].clientX; sy = e.touches[0].clientY; dx = dy = 0; ax = "";
  }, { passive: true });
  hero.addEventListener("touchmove", function (e) {
    if (!on) return;
    dx = e.touches[0].clientX - sx; dy = e.touches[0].clientY - sy;
    if (!ax && (Math.abs(dx) > 10 || Math.abs(dy) > 10)) ax = Math.abs(dx) > Math.abs(dy) ? "x" : "y";
    if (ax === "y" && dy > 0 && npEl.scrollTop <= 0) { npEl.style.transition = "none"; npEl.style.transform = "translateY(" + dy + "px)"; if (e.cancelable) e.preventDefault(); }
    else if (ax === "x") { hero.style.transition = "none"; hero.style.transform = "translateX(" + (dx * .45) + "px)"; hero.style.opacity = String(1 - Math.min(.5, Math.abs(dx) / 420)); }
  }, { passive: false });
  function end() {
    if (!on) return; on = false;
    npEl.style.transition = ""; hero.style.transition = "transform .25s ease,opacity .25s ease";
    var close = ax === "y" && dy > 110 && npEl.scrollTop <= 0;
    npEl.style.transform = ""; hero.style.transform = ""; hero.style.opacity = "";
    if (close) closeNp();
    else if (ax === "x" && Math.abs(dx) > 70) { if (dx < 0) skipNext(); else if (plMode) prevPl(); }
  }
  hero.addEventListener("touchend", end, { passive: true });
  hero.addEventListener("touchcancel", end, { passive: true });
})();

// ---------------------------------------------------------------- sapaan, pencarian ala Spotify, halaman artis
function slotNow() { var h = new Date().getHours(); return h >= 4 && h < 11 ? 0 : h < 15 ? 1 : h < 18 ? 2 : 3; }
function greet() {
  var w = ["Selamat pagi", "Selamat siang", "Selamat sore", "Selamat malam"][slotNow()];
  return w + (ME ? ", " + ME : "");
}
function seedShuf(list) {   // urutan acak yang tetap sama selama satu waktu (pagi/siang/sore/malam) pada hari yang sama
  var d = new Date(), seed = (d.getFullYear() * 400 + d.getMonth() * 31 + d.getDate()) * 4 + slotNow();
  function rnd() { seed = (seed * 1664525 + 1013904223) >>> 0; return seed / 4294967296; }
  var a = list.slice();
  for (var i = a.length - 1; i > 0; i--) { var j = Math.floor(rnd() * (i + 1)), t = a[i]; a[i] = a[j]; a[j] = t; }
  return a;
}
var hist = [];
try { hist = JSON.parse(localStorage.getItem("sp_hist") || "[]") || []; } catch (e) {}
function saveHist() { try { localStorage.setItem("sp_hist", JSON.stringify(hist)); } catch (e) {} }
function addHist(q) {
  q = String(q || "").trim(); if (!q) return;
  hist = hist.filter(function (h) { return h.toLowerCase() !== q.toLowerCase(); }); hist.unshift(q); hist = hist.slice(0, 8); saveHist();
}
function runSearch(q) { $("q").value = q; $("dq").value = q; addHist(q); sfilter = "all"; search(q); }
var GENRES = [["Pop", "pop indonesia", "#e8115b", "\uD83C\uDFA4"], ["Indie", "indie indonesia", "#1e3264", "\uD83C\uDFB8"], ["Hip-Hop", "hip hop indonesia", "#ba5d07", "\uD83C\uDFA7"],
  ["Dangdut", "dangdut", "#8d67ab", "\uD83E\uDD41"], ["Rock", "rock indonesia", "#e13300", "\uD83E\uDD18"], ["Santai", "lagu santai", "#148a08", "\u2615"],
  ["Galau", "lagu galau", "#503750", "\uD83C\uDF27"], ["Semangat", "lagu semangat", "#dc148c", "\u26A1"], ["Akustik", "akustik indonesia", "#477d95", "\uD83C\uDFBB"],
  ["Lo-fi", "lofi", "#7358ff", "\uD83C\uDF19"], ["Jazz", "jazz", "#af2896", "\uD83C\uDFB7"], ["K-Pop", "kpop", "#0d73ec", "\uD83D\uDC96"],
  ["Religi", "sholawat", "#006450", "\uD83D\uDD4C"], ["Viral TikTok", "lagu viral tiktok", "#e61e32", "\uD83D\uDD25"], ["Anak-anak", "lagu anak", "#bc5900", "\uD83C\uDF88"],
  ["Hits 2000-an", "hits 2000an indonesia", "#1e3264", "\uD83D\uDCFC"]];
function drawExplore() {
  var b = $("sex"); b.textContent = "";
  if (hist.length) {
    var h = mk("div", "xh"); h.appendChild(mk("span", "", "Pencarian terakhir"));
    var cl = mk("button", "", "Hapus semua"); cl.addEventListener("click", function () { hist = []; saveHist(); drawExplore(); }); h.appendChild(cl); b.appendChild(h);
    hist.forEach(function (q) {
      var r = mk("div", "hrw"); r.innerHTML = '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>';
      r.appendChild(mk("span", "", q));
      var x = mk("button", "hx", "\u00D7"); x.setAttribute("aria-label", "Hapus");
      x.addEventListener("click", function (e) { e.stopPropagation(); hist = hist.filter(function (z) { return z !== q; }); saveHist(); drawExplore(); });
      r.appendChild(x); r.addEventListener("click", function () { runSearch(q); }); b.appendChild(r);
    });
  }
  b.appendChild(mk("div", "xh", "Jelajahi semua"));
  var g = mk("div", "xg");
  GENRES.forEach(function (gx) {
    var t = mk("div", "xt", gx[0]); t.style.background = gx[2]; t.appendChild(mk("span", "", gx[3]));
    t.addEventListener("click", function () { runSearch(gx[1]); }); g.appendChild(t);
  });
  b.appendChild(g);
}
function drawTop(show) {
  var t = $("stop"), sg = show ? curQuery + "|" + key(items[0]) : "";
  if (t._sig === sg) return; t._sig = sg; t.textContent = ""; if (!show) return;
  var qa = curQuery.toLowerCase(), isArt = false, src = items[0], i;
  for (i = 0; i < items.length; i++) if (primaryArtist(items[i]).toLowerCase() === qa) { isArt = true; src = items[i]; break; }
  t.appendChild(mk("div", "xh", "Hasil teratas"));
  var c = mk("div", "tpc" + (isArt ? " art" : "")); c.appendChild(cvImg(src, ""));
  c.appendChild(mk("div", "tt", isArt ? primaryArtist(src) : src.title));
  c.appendChild(mk("span", "tk", isArt ? "Artis" : "Lagu \u2022 " + src.artist));
  var pb = mk("div", "hpb"); pb.innerHTML = IC_PLAY; c.appendChild(pb);
  c.addEventListener("click", function () { addHist(curQuery); if (isArt) openArtist(primaryArtist(src)); else play(src); });
  if (!isArt) ctx(c, src);
  t.appendChild(c); t.appendChild(mk("div", "xh", "Lagu"));
}
function drawArtistsList() {
  var b = $("sart"), sg = curQuery + "#" + items.length; if (b._sig === sg) return; b._sig = sg; b.textContent = "";
  var qa = curQuery.toLowerCase(), arts = artistsOf(items);
  arts.sort(function (p, q) { return (q.name.toLowerCase() === qa) - (p.name.toLowerCase() === qa); });
  arts.forEach(function (a) {
    var r = mk("div", "arr"); r.appendChild(cvImg({ cover: a.cover }, ""));
    var tx = mk("div", "tx"); tx.appendChild(mk("b", "", a.name)); tx.appendChild(mk("small", "", "Artis")); r.appendChild(tx);
    r.addEventListener("click", function () { addHist(curQuery); openArtist(a.name); }); b.appendChild(r);
  });
}
var sfc = $("sfl").children;
for (var sci = 0; sci < sfc.length; sci++) sfc[sci].addEventListener("click", function () { sfilter = this.getAttribute("data-f"); page = 1; drawSearch(); });
$("dq").addEventListener("focus", function () { if (!this.value && curTab !== "cari") showTab("cari"); });
// ---- halaman artis
var follows = [], arCache = {};
try { follows = JSON.parse(localStorage.getItem("sp_follow") || "[]") || []; } catch (e) {}
function isFol(n) { return follows.some(function (x) { return x.toLowerCase() === n.toLowerCase(); }); }
function toggleFol(n) {
  if (isFol(n)) { follows = follows.filter(function (x) { return x.toLowerCase() !== n.toLowerCase(); }); toast("Berhenti mengikuti " + n, true); }
  else { follows.push(n); toast("Mulai mengikuti " + n, true); }
  try { localStorage.setItem("sp_follow", JSON.stringify(follows)); } catch (e) {}
}
function playList(list, start, shuf) {   // lagu pertama diputar, sisanya masuk antrean
  if (!list || !list.length) return;
  var arr = list.slice(), st = start || 0;
  if (shuf) { for (var i = arr.length - 1; i > 0; i--) { var j = Math.floor(Math.random() * (i + 1)), t = arr[i]; arr[i] = arr[j]; arr[j] = t; } st = 0; }
  var first = arr[st], rest = arr.slice(st + 1, st + 51);
  play(first); queue = rest; qChanged();
}
function openArtist(name) {
  name = String(name || "").trim(); if (!name) return;
  if (!isDesk()) closeNp();
  if (qOpen) closeQ();
  curArtist = name; showTab("art");
  renderArtist(name, arCache[name] || null);
  if (!arCache[name]) {
    api("api/search?q=" + enc(name)).then(function (j) {
      arCache[name] = j.items || [];
      if (curArtist === name && curTab === "art") renderArtist(name, arCache[name]);
    }).catch(function (e) { status("Gagal: " + e.message, false); if (curArtist === name && curTab === "art") renderArtist(name, []); });
  }
}
var SHUFI = '<svg viewBox="0 0 24 24"><path d="M16 3h5v5M4 20L21 3M21 16v5h-5M15 15l6 6M4 4l5 5"/></svg>';
function arRow(it, i, src) {
  var d = mk("div", "pr"); d._k = key(it);
  var n = mk("div", "pn"); n.innerHTML = '<span class="pnn">' + (i + 1) + '</span><svg class="pp" viewBox="0 0 24 24"><path d="M8 4.7c0-.8.9-1.3 1.6-.9l10 6.3c.6.4.6 1.4 0 1.8l-10 6.3c-.7.4-1.6-.1-1.6-.9z"/></svg><span class="eq"><i></i><i></i><i></i></span>';
  var tb = mk("div", "ptb"); tb.appendChild(cvImg(it, "pcv"));
  var tx = mk("div", "tx"); tx.appendChild(mk("div", "t", it.title)); tx.appendChild(mk("div", "a", it.artist)); tb.appendChild(tx);
  var mo = mk("button", "hmore"); mo.innerHTML = DOTS; mo.setAttribute("aria-label", "Opsi lainnya");
  mo.addEventListener("click", function (e) { e.stopPropagation(); openMenu(it, e); });
  d.appendChild(n); d.appendChild(tb); d.appendChild(mk("div", "pd", it.ms ? fmt(it.ms / 1000) : "")); d.appendChild(mo);
  d.addEventListener("click", function () { playList(src, i); });
  ctx(d, it);
  return d;
}
function renderArtist(name, list) {
  var b = $("arbody"); b.textContent = "";
  var own = [], oth = [], nl = name.toLowerCase();
  if (list) list.forEach(function (x) { (String(x.artist || "").toLowerCase().indexOf(nl) >= 0 ? own : oth).push(x); });
  var cov = own[0] || (list && list[0]) || null;
  var h = mk("div", "plh arh");
  var bk = mk("button", "arback"); bk.innerHTML = '<svg viewBox="0 0 24 24"><path d="M15 5l-7 7 7 7"/></svg>'; bk.setAttribute("aria-label", "Kembali");
  bk.addEventListener("click", function () { showTab(lastMain); }); h.appendChild(bk);
  var av = mk("div", "plcov arav"); if (cov) av.appendChild(cvImg(cov, "")); else av.className += " hrt"; h.appendChild(av);
  var pin = mk("div", "plin"); pin.appendChild(mk("div", "pltype", "Artis")); pin.appendChild(mk("h1", "pltitle", name));
  pin.appendChild(mk("div", "plmeta", list ? own.length + " lagu ditemukan" : "Memuat...")); h.appendChild(pin);
  b.appendChild(h);
  if (cov) coverColor(cov, function (c) { h.style.setProperty("--plc", c); });
  if (!list) { var sk = mk("div", ""); skel(sk, 5); b.appendChild(sk); return; }
  var main = own.length ? own : oth;
  if (!main.length) { b.appendChild(mk("div", "empty", "Tidak ada lagu untuk artis ini.")); return; }
  var act = mk("div", "plact");
  var big = mk("button", "plbig"); big.innerHTML = IC_PLAY; big.setAttribute("aria-label", "Putar"); big.addEventListener("click", function () { playList(main, 0, false); });
  var sh = mk("button", "pab"); sh.innerHTML = SHUFI; sh.setAttribute("aria-label", "Putar acak"); sh.addEventListener("click", function () { playList(main, 0, true); toast("Memutar acak", true); });
  var fb = mk("button", "fbtn" + (isFol(name) ? " on" : ""), isFol(name) ? "Mengikuti" : "Ikuti");
  fb.addEventListener("click", function () { toggleFol(name); fb.className = "fbtn" + (isFol(name) ? " on" : ""); fb.textContent = isFol(name) ? "Mengikuti" : "Ikuti"; });
  act.appendChild(big); act.appendChild(sh); act.appendChild(fb); b.appendChild(act);
  b.appendChild(mk("h2", "hh", "Populer"));
  var lst = mk("div", ""), all = main.slice(0, 20);
  all.forEach(function (it, i) { var r = arRow(it, i, main); if (i >= 5) r.classList.add("hide"); lst.appendChild(r); });
  b.appendChild(lst);
  if (all.length > 5) {
    var more = mk("button", "fbtn", "Tampilkan lainnya"); more.style.marginTop = "10px"; var open = false;
    more.addEventListener("click", function () {
      open = !open; var rs = lst.children;
      for (var i = 5; i < rs.length; i++) rs[i].classList.toggle("hide", !open);
      more.textContent = open ? "Tampilkan lebih sedikit" : "Tampilkan lainnya";
    });
    b.appendChild(more);
  }
  var sim = artistsOf(oth).filter(function (a) { return a.name.toLowerCase() !== nl; }).slice(0, 12);
  if (sim.length) {
    var ss = mk("div", "hscroll" + (allOn.arsim ? " all" : ""));
    sim.forEach(function (a) {
      var c = mk("div", "hc hca"); c.appendChild(hcw({ cover: a.cover })); c.appendChild(mk("div", "hn", a.name)); c.appendChild(mk("div", "hs", "Artis"));
      c.addEventListener("click", function () { openArtist(a.name); }); ss.appendChild(c);
    });
    b.appendChild(secHead("arsim", "Artis serupa", ss)); b.appendChild(ss);
  }
  if (oth.length) {
    var so = mk("div", "hscroll" + (allOn.arrel ? " all" : ""));
    oth.slice(0, 14).forEach(function (it) {
      var c = mk("div", "hc"); c.appendChild(hcw(it)); c.appendChild(mk("div", "hn", it.title)); c.appendChild(mk("div", "hs", it.artist));
      c.addEventListener("click", function () { homePlay(it); }); ctx(c, it); so.appendChild(c);
    });
    b.appendChild(secHead("arrel", "Lagu terkait", so)); b.appendChild(so);
  }
  markPl();
}
// ---------------------------------------------------------------- lirik layar penuh
function lfScroll(el, instant) {
  var box = $("lfb"), r = el.getBoundingClientRect(), br = box.getBoundingClientRect();
  smoothScroll(box, box.scrollTop + (r.top - br.top) - box.clientHeight * .3, instant);
}
function lfRender() {
  var inn = $("lfi"); inn.textContent = "";
  $("lft").textContent = cur ? cur.title : ""; $("lfa").textContent = cur ? cur.artist : "";
  if (cur) coverColor(cur, function (c) { $("lyfs").style.setProperty("--lfc", c); }, .8);
  if (!lyr) { inn.appendChild(mk("div", "lfl st", "Lirik belum tersedia.")); return; }
  lyr.lines.forEach(function (ln) {
    var d = mk("div", "lfl" + (lyr.synced ? "" : " st"), ln[1] || "\u266A");
    d.addEventListener("click", function () { if (lyr.synced && ready && ln[0] != null) { au.currentTime = ln[0]; lfUser = 0; } });
    inn.appendChild(d);
  });
  lyIdx = -2; paintLy(true);
}
function lfPaint(force) {
  if (!lyr || !lyr.synced) return;
  var els = $("lfi").children, idx = lyIdx;
  for (var k = 0; k < els.length; k++) {
    var e = els[k], d = Math.abs(k - idx);
    e.className = "lfl" + (k === idx ? " cur" : "");
    e.style.opacity = idx < 0 ? .9 : d === 0 ? 1 : d === 1 ? .72 : d === 2 ? .56 : d === 3 ? .44 : .34;
    e.style.transform = "scale(" + (k === idx ? 1 : .96) + ")";
    e.style.filter = (idx < 0 || d <= 1) ? "none" : "blur(" + Math.min(1.8, (d - 1) * .5).toFixed(2) + "px)";
  }
  if (idx >= 0 && els[idx] && Date.now() - lfUser > 3500) lfScroll(els[idx], !!force);
}
function lfTime() {
  if (!lfOpen || seeking) return;
  var d = au.duration, ok = ready && d && isFinite(d);
  $("lfbar").style.width = ok ? (au.currentTime / d * 100) + "%" : "0";
  $("lfcur").textContent = ok ? fmt(au.currentTime) : "0:00"; $("lfdur").textContent = ok ? fmt(d) : "";
}
function openLy() {
  if (!cur || !lyr) return;
  lfOpen = true; lfUser = 0; $("lyfs").className = "lyfs"; lfRender(); lfTime(); setIc($("lfplay"), ready && !au.paused);
}
function closeLy() { if (!lfOpen) return; lfOpen = false; $("lyfs").className = "lyfs closed"; }
$("lfopen").addEventListener("click", function (e) { e.stopPropagation(); openLy(); });
$("lfx").addEventListener("click", closeLy);
$("lfplay").addEventListener("click", function () { $("pbtn").click(); });
$("lfprev").addEventListener("click", function () { if (plMode) prevPl(); else au.currentTime = 0; });
$("lfnext").addEventListener("click", function () { skipNext(); });
["wheel", "touchstart"].forEach(function (n) { $("lfb").addEventListener(n, function () { lfUser = Date.now(); }, { passive: true }); });
au.addEventListener("timeupdate", function () { if (lfOpen) { paintLy(false); lfTime(); } });
dragBar($("lfbarw"), "lfbar", "lfcur");
// ---------------------------------------------------------------- timer tidur, crossfade, pengaturan
try { cf = +localStorage.getItem("sp_cf") || 0; } catch (e) {}
function sleepUi() {
  var on = !!(sleepAt || sleepEnd), txt = sleepAt ? Math.max(1, Math.ceil((sleepAt - Date.now()) / 60000)) + "m" : sleepEnd ? "1" : "";
  [["dsb", "dsleep", "dbtn"], ["npsb", "npsleep", "npb"]].forEach(function (x) {
    var bd = $(x[0]); bd.textContent = txt; bd.className = on ? "bd" : "bd hide"; $(x[1]).className = x[2] + (on ? " on" : "");
  });
}
function clearSleep() { sleepAt = 0; sleepEnd = false; clearInterval(sleepT); sleepT = null; sleepUi(); }
function fadePause() {
  var v0 = au.volume, t0 = performance.now(), dur = 4000;
  (function step() {
    var k = Math.min(1, (performance.now() - t0) / dur);
    au.volume = v0 * (1 - k);
    if (k < 1) setTimeout(step, 80); else { au.pause(); au.volume = v0; }
  })();
}
function sleepTick() {
  if (sleepAt && Date.now() >= sleepAt) { clearSleep(); fadePause(); toast("Timer tidur: pemutaran dihentikan", true); status("Timer tidur: pemutaran dihentikan."); return; }
  sleepUi();
}
function setSleep(min) {
  clearSleep();
  if (min === "end") { sleepEnd = true; toast("Berhenti di akhir lagu ini", true); }
  else { sleepAt = Date.now() + min * 60000; toast("Timer tidur: " + min + " menit", true); }
  sleepT = setInterval(sleepTick, 1000); sleepUi();
}
function openSleepMenu(ev) {
  var acts = [];
  if (sleepAt || sleepEnd) acts.push(["Matikan timer", function () { clearSleep(); toast("Timer tidur dimatikan", true); }]);
  [5, 10, 15, 30, 45, 60].forEach(function (m) { acts.push([m + " menit", function () { setSleep(m); }]); });
  acts.push(["Akhir lagu ini", function () { setSleep("end"); }, sleepEnd]);
  showMenu(acts, ev, mk("div", "cmh", "Timer tidur"));
}
function openCfMenu(ev) {
  var acts = [["Mati", 0], ["3 detik", 3], ["6 detik", 6], ["9 detik", 9], ["12 detik", 12]].map(function (o) {
    return [o[0], function () { cf = o[1]; try { localStorage.setItem("sp_cf", String(cf)); } catch (e) {} toast(cf ? "Crossfade: " + cf + " detik" : "Crossfade dimatikan", true); }, cf === o[1]];
  });
  showMenu(acts, ev, mk("div", "cmh", "Crossfade"));
}
function openSettings(ev) {
  var rem = sleepAt ? Math.max(1, Math.ceil((sleepAt - Date.now()) / 60000)) + " mnt" : sleepEnd ? "akhir lagu" : "mati";
  var acts = [
    ["Timer tidur \u00B7 " + rem, function () { setTimeout(function () { openSleepMenu(ev); }, 0); }],
    ["Crossfade \u00B7 " + (cf ? cf + " detik" : "mati"), function () { setTimeout(function () { openCfMenu(ev); }, 0); }]
  ];
  if (hist.length) acts.push(["Hapus riwayat pencarian", function () { hist = []; saveHist(); if (curTab === "cari") drawSearch(); toast("Riwayat pencarian dihapus", true); }]);
  showMenu(acts, ev, mk("div", "cmh", "Pengaturan"));
}
function killTail() { clearInterval(tailT); tailT = null; if (tail) { try { tail.pause(); tail.removeAttribute("src"); } catch (e) {} tail = null; } }
function startCrossfade() {   // lagu lama tetap berbunyi di pemutar cadangan sambil memudar, lagu baru memudar masuk
  cfDone = true;
  var t = new Audio(), pos = au.currentTime, v0 = au.volume, before = pseq;
  t.src = au.src; t.volume = v0;
  t.addEventListener("loadedmetadata", function () { try { t.currentTime = pos + 0.3; } catch (e) {} }, { once: true });
  skipNext();
  if (pseq === before) return;   // tidak ada lagu berikutnya
  killTail(); tail = t; t.play().catch(function () {});
  var dur = cf * 1000, t0 = performance.now(); au.volume = 0;
  tailT = setInterval(function () {
    var k = Math.min(1, (performance.now() - t0) / dur);
    try { t.volume = Math.max(0, v0 * (1 - k)); } catch (e) {}
    au.volume = uvol * k;
    if (k >= 1) { killTail(); au.volume = uvol; }
  }, 60);
}
$("dsleep").addEventListener("click", openSleepMenu);
$("npsleep").addEventListener("click", openSleepMenu);
$("hav").addEventListener("click", openSettings);
$("dav").addEventListener("click", openSettings);
sleepUi();
loadPl();
showTab("home");
drawSearch();

})();
</script>
</body></html>
"""

if __name__ == "__main__":
    srv = ThreadingHTTPServer((HOST, PORT), H)
    print("Mini App lagu berjalan di http://%s:%d  (sumber: %s)" % (HOST, PORT, SRC), flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass

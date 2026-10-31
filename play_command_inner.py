# Diekstrak dari telegram-control-local-opensource.sh baris 723-753
# Fungsi shell asal: play_command_inner()
# Dipanggil lewat: python - "$q" "$PLAY_SEARCH_N" "${ck[@]}" <<'PY' > "$d/meta.json" 2>/dev/null
import sys, json, subprocess, datetime, re
q, n, *ck = sys.argv[1:]
n = max(1, int(n))
# 1) cari n hasil teratas (cepat, tanpa membuka tiap video), pilih yang penontonnya terbanyak
r = subprocess.run(["yt-dlp", "--no-playlist", "--no-warnings", "--flat-playlist", "--dump-single-json", *ck, "ytsearch%d:%s" % (n, q)],
                   capture_output=True, text=True, timeout=150)
ents = [x for x in (json.loads(r.stdout).get("entries") or []) if x and x.get("id")]
# hanya hasil yang paling banyak memuat kata kunci (di judul / nama channel) yang bersaing; di antaranya dipilih penonton terbanyak
toks = re.findall(r"\w+", q.lower())
def score(x):
    hay = " ".join(str(x.get(k) or "") for k in ("title", "channel", "uploader")).lower()
    return sum(1 for t in toks if t in hay)
top = max(score(x) for x in ents)
cands = [x for x in ents if score(x) == top] if top > 0 else ents[:1]
best = max(cands, key=lambda x: x.get("view_count") or 0)
# 2) ambil data lengkap video terpilih (tanggal upload dll)
r = subprocess.run(["yt-dlp", "--no-playlist", "--no-warnings", "--dump-single-json", *ck, "https://www.youtube.com/watch?v=" + best["id"]],
                   capture_output=True, text=True, timeout=150)
e = json.loads(r.stdout)
dur = int(e.get("duration") or 0)
views = e.get("view_count")
vt = f"{int(views):,}".replace(",", ".") if views is not None else "-"
dt = f"{dur // 3600}:{dur % 3600 // 60:02d}:{dur % 60:02d}" if dur >= 3600 else f"{dur // 60}:{dur % 60:02d}"
ago = "-"
try:
    days = (datetime.date.today() - datetime.datetime.strptime(e["upload_date"], "%Y%m%d").date()).days
    ago = "hari ini" if days < 1 else f"{days} hari lalu" if days < 30 else f"{days // 30} bulan lalu" if days < 365 else f"{days // 365} tahun lalu"
except Exception:
    pass
print(json.dumps({"id": e.get("id"), "title": e.get("title"), "chan": e.get("channel") or e.get("uploader") or "-",
                  "views": vt, "dur": dt, "ago": ago, "secs": dur, "ok": 1}))

# Diekstrak dari telegram-control-local-opensource.sh baris 1122-1153
# Fungsi shell asal: tiktok_command_inner()
# Dipanggil lewat: python - "$d" <<'PY' > "$d/plan.txt" 2>/dev/null
import json, sys, os
d = sys.argv[1]
try:
    j = json.load(open(os.path.join(d, "api.json")))
    x = j["data"]
except Exception:
    sys.exit(1)
def full(u):
    if not u: return ""
    return "https://www.tikwm.com" + u if u.startswith("/") else u
clean = lambda s: (s or "").replace("\n", " ").replace("|", "/").strip()
a = x.get("author") or {}
imgs = [full(u) for u in (x.get("images") or []) if u]
print("TITLE|" + clean(x.get("title"))[:300])
open(os.path.join(d, "desc.txt"), "w", encoding="utf-8").write(x.get("title") or "")
def num(v):
    try: return f"{int(v):,}".replace(",", ".")
    except Exception: return "-"
sec = int(x.get("duration") or 0)
dur = f"{sec // 3600}:{sec % 3600 // 60:02d}:{sec % 60:02d}" if sec >= 3600 else f"{sec // 60}:{sec % 60:02d}"
tipe = ("Slideshow foto (%d foto)" % len(imgs)) if imgs else "Tanpa watermark"
json.dump({"secs": sec, "dur": dur, "views": num(x.get("play_count")), "comments": num(x.get("comment_count")),
           "shares": num(x.get("share_count")), "tipe": tipe},
          open(os.path.join(d, "stats.json"), "w", encoding="utf-8"))
print("AUTHOR|" + clean(a.get("nickname") or a.get("unique_id")))
print("MUSIC|" + full(x.get("music")))
if imgs:
    print("KIND|photo")
    for u in imgs: print("IMG|" + u)
else:
    print("KIND|video")
    print("VIDEO|" + full(x.get("hdplay") or x.get("play")))

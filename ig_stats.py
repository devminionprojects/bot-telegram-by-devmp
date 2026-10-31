# Diekstrak dari telegram-control-local-opensource.sh baris 1324-1355
# Fungsi shell asal: ig_stats()
# Dipanggil lewat: python3 - "$1" <<'PYS' 2>/dev/null
import sys, os, json, glob
d = sys.argv[1]
j = {}
try: j = json.load(open(os.path.join(d, "meta.json")))
except Exception: pass
ents = [e for e in (j.get("entries") or []) if e] or [j]
first = ents[0] if ents else {}
num = lambda v: ("{:,}".format(int(v)).replace(",", ".")) if isinstance(v, (int, float)) else "-"
IMG = (".jpg", ".jpeg", ".png", ".webp"); VID = (".mp4", ".mov", ".webm", ".mkv")
fs = [f for f in glob.glob(os.path.join(d, "m_*")) if not f.endswith(".json")]
nv = sum(1 for f in fs if f.lower().endswith(VID)); ni = sum(1 for f in fs if f.lower().endswith(IMG))
if nv and ni: tipe = "Carousel (%d foto, %d video)" % (ni, nv)
elif len(fs) > 1: tipe = ("Carousel (%d video)" % nv) if nv else ("Carousel (%d foto)" % ni)
elif nv: tipe = "Video / Reel"
else: tipe = "Foto"
dur = first.get("duration")
if not isinstance(dur, (int, float)) or dur <= 0:
    try:
        import subprocess
        vf = sorted(f for f in fs if f.lower().endswith(VID))[0]
        dur = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", vf], timeout=30).decode().strip())
    except Exception:
        dur = None
dur_t = "-"
if isinstance(dur, (int, float)) and dur > 0:
    dur = int(dur); dur_t = "%d:%02d" % (dur // 60, dur % 60)
who = j.get("uploader") or first.get("uploader") or j.get("channel") or first.get("channel") or "-"
json.dump({"akun": ("@" + who) if who != "-" and not str(who).startswith("@") else who, "tipe": tipe, "suka": num(first.get("like_count") or j.get("like_count")),
           "komentar": num(first.get("comment_count") or j.get("comment_count")), "views": num(first.get("view_count") or j.get("view_count")),
           "dur": dur_t, "secs": int(dur) if isinstance(dur, (int, float)) and dur > 0 else 0, "video": bool(nv)}, open(os.path.join(d, "stats.json"), "w"))
desc = j.get("description") or first.get("description") or j.get("title") or first.get("title") or ""
open(os.path.join(d, "desc.txt"), "w", encoding="utf-8").write(desc)

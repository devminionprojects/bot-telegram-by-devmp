# Diekstrak dari telegram-control-local-opensource.sh baris 1656-1691
# Fungsi shell asal: ytdl_stats()
# Dipanggil lewat: python3 - "$1" "$2" "$3" <<'PYS_YT' 2>/dev/null
import sys, os, json, subprocess, datetime
d, f, mode = sys.argv[1:4]
try: j = json.load(open(os.path.join(d, "meta.json")))
except Exception: j = {}
num = lambda v: ("{:,}".format(int(v)).replace(",", ".")) if isinstance(v, (int, float)) else "-"
secs = int(j.get("duration") or 0)
def hms(s):
    return "%d:%02d:%02d" % (s // 3600, s % 3600 // 60, s % 60) if s >= 3600 else "%d:%02d" % (s // 60, s % 60)
ago = "-"
try:
    days = (datetime.date.today() - datetime.datetime.strptime(j["upload_date"], "%Y%m%d").date()).days
    ago = "hari ini" if days < 1 else "%d hari lalu" % days if days < 30 else "%d bulan lalu" % (days // 30) if days < 365 else "%d tahun lalu" % (days // 365)
except Exception: pass
ext = os.path.splitext(f)[1].lower().lstrip(".")
size = os.path.getsize(f)
size_t = ("%.1f MB" % (size / 1048576.0)).replace(".", ",") if size >= 1048576 else "%d KB" % max(1, size // 1024)
s = {}
try:
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0" if mode == "video" else "a:0",
                        "-show_entries", "stream=height,bit_rate", "-of", "json", f], capture_output=True, text=True, timeout=30)
    s = (json.loads(r.stdout).get("streams") or [{}])[0]
except Exception: pass
if mode == "video":
    tipe = "Video %s" % ext.upper() + ((" \u00B7 %sp" % s["height"]) if s.get("height") else "")
    if "/shorts/" in (j.get("webpage_url") or ""): tipe += " \u00B7 Shorts"
else:
    br = str(s.get("bit_rate") or "")
    tipe = "Audio %s" % ext.upper() + ((" \u00B7 %d kbps" % round(int(br) / 1000.0)) if br.isdigit() else "")
title = j.get("title") or "-"
chan = j.get("channel") or j.get("uploader") or "-"
rows = [["\U0001F3AC", "Judul", title[:150]], ["\U0001F4FA", "Channel", chan], ["\U0001F3F7\uFE0F", "Tipe", tipe],
        ["\u23F1\uFE0F", "Durasi", hms(secs) if secs > 0 else "-"], ["\U0001F441\uFE0F", "Views", num(j.get("view_count"))],
        ["\U0001F44D", "Suka", num(j.get("like_count"))], ["\U0001F4AC", "Komentar", num(j.get("comment_count"))],
        ["\U0001F4C5", "Upload", ago], ["\U0001F4E6", "Ukuran", size_t]]
json.dump({"rows": rows, "secs": secs, "title": title, "chan": chan}, open(os.path.join(d, "stats.json"), "w"))
open(os.path.join(d, "desc.txt"), "w", encoding="utf-8").write(j.get("description") or "")

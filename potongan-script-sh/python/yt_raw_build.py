# Diekstrak dari telegram-control-local-opensource.sh baris 297-380
# Fungsi shell asal: yt_raw_build()
# Dipanggil lewat: python - "$d" "$url" "${YT_RAW_TIMESTAMP:-1}" "$forced" "${ck[@]}" <<'PY'
import sys, json, subprocess, glob, re, html, os
d, url, ts, forced, *ck = sys.argv[1:]
r = subprocess.run(["yt-dlp", "--skip-download", "--no-playlist", "-J", *ck, url],
                   capture_output=True, text=True, timeout=180)
try:
    j = json.loads(r.stdout)
except Exception:
    sys.exit(2)
manual = {k: v for k, v in (j.get("subtitles") or {}).items() if k != "live_chat"}
auto = j.get("automatic_captions") or {}
vl = (j.get("language") or "").split("-")[0].lower()   # bahasa ucapan video menurut YouTube (kalau diketahui)
lang = kind = None
if forced:
    # bahasa dipaksa pengguna (yt mentah id / ytraw en link)
    ks = [k for k in manual if k == forced or k.startswith(forced + "-")]
    if ks: lang, kind = ks[0], "manual"
    else:
        for cand in (forced + "-orig", forced):
            if cand in auto: lang, kind = cand, "auto"; break
    if not lang: sys.exit(4)
else:
    # 1) subtitle buatan pemilik: bahasa ucapan video dulu, lalu id, lalu en
    for cand in [c for c in (vl, "id", "en") if c]:
        ks = [k for k in manual if k == cand or k.startswith(cand + "-")]
        if ks: lang, kind = ks[0], "manual"; break
    # 2) subtitle otomatis: bahasa ucapan video dulu, lalu trek asli (-orig) dengan id didahulukan dari en, lalu id, en
    if not lang:
        order = ([vl + "-orig", vl] if vl else []) + ["id-orig", "en-orig", "id", "en"]
        for cand in order:
            if cand in auto: lang, kind = cand, "auto"; break
        if not lang:
            orig = [k for k in auto if k.endswith("-orig")]
            if orig: lang, kind = orig[0], "auto"
    if not lang and manual:
        lang, kind = next(iter(manual)), "manual"
if not lang:
    sys.exit(3)
subprocess.run(["yt-dlp", "--skip-download", "--no-playlist", *ck,
                "--write-subs" if kind == "manual" else "--write-auto-subs",
                "--sub-langs", lang, "--sub-format", "vtt", "-o", os.path.join(d, "s"), url],
               capture_output=True, text=True, timeout=300)
files = sorted(glob.glob(os.path.join(d, "s*.vtt")))
if not files:
    sys.exit(3)
raw = open(files[0], encoding="utf-8", errors="replace").read().replace("\r", "")

def secs(t):
    p = t.strip().split(":")
    p = [float(x) for x in p]
    while len(p) < 3: p.insert(0, 0.0)
    return int(p[0] * 3600 + p[1] * 60 + p[2])

def stamp(s):
    h, m, sec = s // 3600, (s % 3600) // 60, s % 60
    return f"[{h}:{m:02d}:{sec:02d}]" if h else f"[{m:02d}:{sec:02d}]"

lines_out, last = [], None
for block in re.split(r"\n\s*\n", raw):
    bl = block.split("\n")
    idx = next((i for i, l in enumerate(bl) if "-->" in l), None)
    if idx is None: continue
    start = secs(bl[idx].split("-->")[0])
    for l in bl[idx + 1:]:
        t = html.unescape(re.sub(r"<[^>]*>", "", l)).strip()
        if not t: continue
        # subtitle otomatis YouTube mengulang baris yang sama berturut-turut (efek bergulir): buang pengulangan itu saja
        if kind == "auto" and t == last: continue
        last = t
        lines_out.append((start, t))

title = j.get("title") or "video"
ud = j.get("upload_date") or ""
if len(ud) == 8: ud = f"{ud[6:8]}-{ud[4:6]}-{ud[:4]}"
dur = j.get("duration") or 0
head = [f"Judul: {title}", f"Kanal: {j.get('channel') or '-'}", f"Tanggal unggah: {ud or '-'}",
        f"Durasi: {dur // 3600}:{(dur % 3600) // 60:02d}:{dur % 60:02d}", f"Link: {url}",
        f"Subtitle: {lang} ({'buatan pemilik video' if kind == 'manual' else 'otomatis YouTube'})"
        + (" - kemungkinan terjemahan mesin, bukan ucapan asli" if kind == "auto" and not lang.endswith("-orig") and vl and vl != lang[:2] else ""),
        "Isi di bawah ini adalah transkrip mentah dari subtitle, tanpa diubah AI.", "", "TRANSKRIP:"]
open(os.path.join(d, "head.txt"), "w", encoding="utf-8").write("\n".join(head) + "\n")
open(os.path.join(d, "lines.tsv"), "w", encoding="utf-8").write("".join(f"{s}\t{t.replace(chr(9), ' ')}\n" for s, t in lines_out))
open(os.path.join(d, "info.txt"), "w").write(lang)
safe = re.sub(r"[^A-Za-z0-9._-]+", "_", title).strip("_")[:60] or "video"
open(os.path.join(d, "fname.txt"), "w").write(f"transkrip_{safe}.txt")

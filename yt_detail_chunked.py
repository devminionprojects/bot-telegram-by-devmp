# Diekstrak dari telegram-control-local-opensource.sh baris 178-195
# Fungsi shell asal: yt_detail_chunked()
# Dipanggil lewat: n=$(python - "$d" "${YT_DETAIL_CHUNK:-24000}" <<'PY'
import sys, os
d, lim = sys.argv[1], int(sys.argv[2])
t = open(os.path.join(d, "data.txt"), encoding="utf-8").read()
meta, _, tr = t.partition("TRANSKRIP:\n")
open(os.path.join(d, "meta.txt"), "w", encoding="utf-8").write(meta[:2500])
parts, cur, size = [], [], 0
for ln in tr.split("\n"):
    while len(ln) > lim:
        if cur: parts.append("\n".join(cur)); cur, size = [], 0
        parts.append(ln[:lim]); ln = ln[lim:]
    if cur and size + len(ln) + 1 > lim:
        parts.append("\n".join(cur)); cur, size = [], 0
    cur.append(ln); size += len(ln) + 1
if cur: parts.append("\n".join(cur))
parts = [p for p in parts if p.strip()]
for i, p in enumerate(parts, 1):
    open(os.path.join(d, f"p{i:04d}.txt"), "w", encoding="utf-8").write(p)
print(len(parts))

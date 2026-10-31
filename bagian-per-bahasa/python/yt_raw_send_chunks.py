# Diekstrak dari telegram-control-local-opensource.sh baris 472-487
# Fungsi shell asal: yt_raw_send_chunks()
# Dipanggil lewat: python - "$f" "$dir" <<'PY'
import sys, os
f, d = sys.argv[1:]
lim = 3500
chunks, cur, size = [], [], 0
for ln in open(f, encoding="utf-8").read().split("\n"):
    while len(ln) > lim:
        if cur: chunks.append("\n".join(cur)); cur, size = [], 0
        chunks.append(ln[:lim]); ln = ln[lim:]
    if cur and size + len(ln) + 1 > lim:
        chunks.append("\n".join(cur)); cur, size = [], 0
    cur.append(ln); size += len(ln) + 1
if cur: chunks.append("\n".join(cur))
chunks = [c for c in chunks if c.strip()]
for i, c in enumerate(chunks, 1):
    open(os.path.join(d, f"{i:06d}.txt"), "w", encoding="utf-8").write(c)
print(len(chunks))

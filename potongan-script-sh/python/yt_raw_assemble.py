# Diekstrak dari telegram-control-local-opensource.sh baris 387-402
# Fungsi shell asal: yt_raw_assemble()
# Dipanggil lewat: python - "$1" "$2" "${YT_RAW_TIMESTAMP:-1}" <<'PY'
import sys, os
d, mode, ts = sys.argv[1:4]
head = open(os.path.join(d, "head.txt"), encoding="utf-8").read().rstrip("\n").split("\n")
if mode == "terj":
    head = [h + "; diterjemahkan ke Bahasa Indonesia oleh AI per baris" if h.startswith("Subtitle:") else h for h in head]
    head = ["Isi di bawah ini adalah transkrip LENGKAP dari subtitle, diterjemahkan per baris oleh AI tanpa diringkas atau dikurangi. Jam dan urutan sama dengan subtitle asli." if h.startswith("Isi di bawah ini") else h for h in head]
src = os.path.join(d, "lines_id.tsv" if mode == "terj" else "lines.tsv")
def stamp(s):
    h, m, sec = s // 3600, (s % 3600) // 60, s % 60
    return f"[{h}:{m:02d}:{sec:02d}]" if h else f"[{m:02d}:{sec:02d}]"
body = []
for ln in open(src, encoding="utf-8").read().split("\n"):
    if not ln.strip(): continue
    a, _, t = ln.partition("\t")
    body.append(f"{stamp(int(a))} {t}" if ts == "1" else t)
open(os.path.join(d, "out.txt"), "w", encoding="utf-8").write("\n".join(head + body) + "\n")

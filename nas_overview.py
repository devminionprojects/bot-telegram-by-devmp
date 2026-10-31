# Diekstrak dari telegram-control-local-opensource.sh baris 4358-4396
# Fungsi shell asal: nas_overview()
# Dipanggil lewat: out=$(python - "$(nas_root)" <<'PY'
import os, sys
root = sys.argv[1]
IMG = ('.jpg', '.jpeg', '.png', '.webp')
VID = ('.mp4', '.mov', '.3gp', '.mkv')
rows = []
if os.path.isdir(root):
    for d in os.listdir(root):
        full = os.path.join(root, d)
        if not os.path.isdir(full):
            continue
        parts = d.split('-')
        if len(parts) != 3:
            continue
        files = [f for f in os.listdir(full) if os.path.isfile(os.path.join(full, f))]
        if not files:
            continue
        img = sum(1 for f in files if f.lower().endswith(IMG))
        vid = sum(1 for f in files if f.lower().endswith(VID))
        size = sum(os.path.getsize(os.path.join(full, f)) for f in files)
        rows.append((parts[2], parts[1], parts[0], d, len(files), img, vid, len(files) - img - vid, size))
rows.sort()
if not rows:
    print('__KOSONG__')
    sys.exit(0)
def fmt(b):
    for u in ('B', 'KB', 'MB', 'GB'):
        if b < 1024 or u == 'GB':
            return ('%d %s' % (b, u)) if u == 'B' else ('%.1f %s' % (b, u))
        b /= 1024.0
T = [0, 0, 0, 0, 0]
lines = []
for r in rows:
    lines.append('📅 %s: %d file (🖼 %d foto, 🎬 %d video, 📄 %d lainnya) - %s' % (r[3], r[4], r[5], r[6], r[7], fmt(r[8])))
    T[0] += r[4]; T[1] += r[5]; T[2] += r[6]; T[3] += r[7]; T[4] += r[8]
print('\n'.join(lines))
print('')
print('📦 TOTAL: %d tanggal, %d file' % (len(rows), T[0]))
print('🖼 Foto: %d | 🎬 Video: %d | 📄 File lain: %d' % (T[1], T[2], T[3]))
print('💾 Ukuran: %s' % fmt(T[4]))

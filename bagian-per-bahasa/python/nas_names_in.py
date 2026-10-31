# Diekstrak dari telegram-control-local-opensource.sh baris 3314-3326
# Fungsi shell asal: nas_names_in()
# Dipanggil lewat: python - "$1" "$2" <<'PY'
import os, sys
folder, kind = sys.argv[1], sys.argv[2]
IMG = ('.jpg', '.jpeg', '.png', '.webp')
VID = ('.mp4', '.mov', '.3gp', '.mkv')
if not os.path.isdir(folder):
    sys.exit(0)
for f in sorted(os.listdir(folder)):
    if not os.path.isfile(os.path.join(folder, f)):
        continue
    low = f.lower()
    k = 'foto' if low.endswith(IMG) else ('video' if low.endswith(VID) else 'file')
    if not kind or k == kind:
        print(f)

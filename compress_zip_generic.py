# Diekstrak dari telegram-control-local-opensource.sh baris 3019-3023
# Fungsi shell asal: compress_zip_generic()
# Dipanggil lewat: python3 - "$in" "$out" <<'PYZ'
import sys, zipfile, os
src, dst = sys.argv[1], sys.argv[2]
with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    z.write(src, os.path.basename(src))
sys.exit(0 if os.path.getsize(dst) < os.path.getsize(src) * 0.95 else 1)

# Diekstrak dari telegram-control-local-opensource.sh baris 2892-2924
# Fungsi shell asal: compress_image()
# Dipanggil lewat: python3 - "$in" "$out" "$((tb * COMPRESS_MARGIN / 100))" "$tb" <<'PYI'
import sys, io, os
from PIL import Image, ImageOps
src, dst, aim, tb = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
im = Image.open(src)
im = ImageOps.exif_transpose(im)
webp = dst.lower().endswith(".webp")
if im.mode in ("RGBA", "LA", "P"):
    im = im.convert("RGBA")
    bg = Image.new("RGB", im.size, (255, 255, 255)); bg.paste(im, mask=im.split()[-1]); im = bg
else:
    im = im.convert("RGB")
def enc(img, q):
    b = io.BytesIO()
    if webp: img.save(b, "WEBP", quality=q, method=4)
    else:    img.save(b, "JPEG", quality=q, optimize=True, progressive=True)
    return b.getvalue()
scales = [1.0, 0.85, 0.7, 0.55, 0.42, 0.32, 0.24, 0.18, 0.12]
best = None
for i, s in enumerate(scales):
    w, h = max(1, int(im.width * s)), max(1, int(im.height * s))
    img = im.resize((w, h), Image.LANCZOS) if s < 1 else im
    lo, hi, fit = 20, 95, None
    while lo <= hi:                      # cari kualitas tertinggi yang masih muat
        mid = (lo + hi) // 2
        data = enc(img, mid)
        if len(data) <= aim: fit, lo = (mid, data), mid + 1
        else: hi = mid - 1
    if fit and (fit[0] >= 55 or i == len(scales) - 1):
        best = fit[1]; break              # kualitas masih bagus -> cukup; kalau jelek, perkecil dimensi dulu
    if fit: best = fit[1]
    else: best = enc(img, 20)
open(dst, "wb").write(best)
sys.exit(0 if len(best) <= tb else 2)

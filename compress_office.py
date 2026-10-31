# Diekstrak dari telegram-control-local-opensource.sh baris 2972-3011
# Fungsi shell asal: compress_office()
# Dipanggil lewat: python3 - "$in" "$out" "$((tb * COMPRESS_MARGIN / 100))" "$tb" <<'PYO'
import sys, io, zipfile, os
from PIL import Image
src, dst, aim, tb = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
zin = zipfile.ZipFile(src)
infos = zin.infolist()
raw = {i.filename: zin.read(i.filename) for i in infos}
def shrink(name, data, q, maxdim):
    low = name.lower()
    if "/media/" not in low or not low.endswith((".jpg", ".jpeg", ".png")): return data
    try:
        im = Image.open(io.BytesIO(data)); im.load()
    except Exception:
        return data
    if max(im.size) > maxdim:
        r = maxdim / max(im.size); im = im.resize((max(1, int(im.width * r)), max(1, int(im.height * r))), Image.LANCZOS)
    b = io.BytesIO()
    if low.endswith(".png"):
        if im.mode in ("RGBA", "LA"):
            im.save(b, "PNG", optimize=True)
        else:
            im.convert("P", palette=Image.ADAPTIVE, colors=256 if q > 40 else 64).save(b, "PNG", optimize=True)
    else:
        im.convert("RGB").save(b, "JPEG", quality=q, optimize=True)
    out = b.getvalue()
    return out if len(out) < len(data) else data
def build(q, maxdim):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for i in infos:
            z.writestr(i.filename, shrink(i.filename, raw[i.filename], q, maxdim) if q else raw[i.filename])
    return buf.getvalue()
best = None
for q, md in [(0, 0), (85, 2400), (70, 1800), (55, 1400), (42, 1000), (32, 720), (24, 480)]:
    data = build(q, md)
    if best is None or len(data) < len(best): best = data
    if len(best) <= aim: break
if len(best) >= os.path.getsize(src):
    sys.exit(1)
open(dst, "wb").write(best)
sys.exit(0 if len(best) <= tb else 2)

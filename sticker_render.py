# Diekstrak dari telegram-control-local-opensource.sh baris 7091-7161
# Fungsi shell asal: sticker_render()
# Dipanggil lewat: STICKER_FONT="$STICKER_FONT" python - "$1" "$2" <<'PY'
import os, sys
from PIL import Image, ImageDraw, ImageFont
src, out = sys.argv[1], sys.argv[2]
words = open(src, encoding='utf-8').read().upper().split()
if not words:
    sys.exit(2)
W, PAD, RADIUS = 512, 36, 44
inner_w, max_h = W - 2 * PAD, 512 - 2 * PAD
FONTS = [os.environ.get('STICKER_FONT', ''),
         '/system/fonts/RobotoCondensed-Bold.ttf', '/system/fonts/Roboto-Bold.ttf',
         '/system/fonts/DroidSans-Bold.ttf', '/system/fonts/Roboto-Regular.ttf',
         '/data/data/com.termux/files/usr/share/fonts/TTF/DejaVuSans-Bold.ttf',
         'DejaVuSans-Bold.ttf', 'LiberationSans-Bold.ttf', 'Arial Bold.ttf']
def font(sz):
    for p in FONTS:
        if not p:
            continue
        try:
            return ImageFont.truetype(p, sz)
        except Exception:
            pass
    return ImageFont.load_default(sz)
def wrap(f):
    lines, cur = [], []
    for w in words:
        if f.getlength(w) > inner_w:
            return None
        trial = ' '.join(cur + [w])
        if cur and f.getlength(trial) > inner_w:
            lines.append(cur); cur = [w]
        else:
            cur.append(w)
    lines.append(cur)
    return lines
chosen = None
for sz in range(150, 17, -2):
    f = font(sz)
    ls = wrap(f)
    if ls is None:
        continue
    asc, desc = f.getmetrics()
    lh = asc + desc
    if lh * len(ls) <= max_h:
        chosen = (f, ls, lh); break
if chosen is None:
    f = font(18); ls = wrap(f) or [words]; asc, desc = f.getmetrics(); chosen = (f, ls, asc + desc)
f, lines, lh = chosen
H = max(140, min(512, lh * len(lines) + 2 * PAD))
img = Image.new('RGBA', (W, H), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
d.rounded_rectangle((0, 0, W - 1, H - 1), radius=RADIUS, fill=(255, 255, 255, 255))
y = PAD
for i, ln in enumerate(lines):
    if i < len(lines) - 1 and len(ln) > 1:
        gap = (inner_w - sum(f.getlength(w) for w in ln)) / (len(ln) - 1)
        x = float(PAD)
        for w in ln:
            d.text((x, y), w, font=f, fill=(20, 20, 20, 255))
            x += f.getlength(w) + gap
    else:
        d.text((PAD, y), ' '.join(ln), font=f, fill=(20, 20, 20, 255))
    y += lh
try:
    q = 95
    img.save(out, 'WEBP', quality=q)
    while os.path.getsize(out) > 500000 and q > 40:
        q -= 15; img.save(out, 'WEBP', quality=q)
    print('webp')
except Exception:
    img.save(out, 'PNG')
    print('png')

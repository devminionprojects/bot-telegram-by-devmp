# Diekstrak dari telegram-control-local-opensource.sh baris 1288-1317
# Fungsi shell asal: ig_embed_plan()
# Dipanggil lewat: IG_UA="$IG_UA" python3 - "$1" "$2" <<'PYE' 2>/dev/null
import sys, re, json, os, html, urllib.request
url, d = sys.argv[1:3]
m = re.search(r'instagram\.com/(?:[^/]+/)?(?:p|reel|reels|tv)/([A-Za-z0-9_-]+)', url)
if not m:
    sys.exit(1)
req = urllib.request.Request("https://www.instagram.com/p/%s/embed/captioned/" % m.group(1),
                             headers={"User-Agent": os.environ.get("IG_UA", "Mozilla/5.0")})
try:
    raw = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
except Exception:
    sys.exit(1)
t = raw.replace('\\"', '"').replace('\\/', '/')
def dec(x):
    try: return json.loads('"' + x + '"')
    except Exception: return x.replace('\\u0026', '&')
vids, imgs = [], []
for x in re.findall(r'"video_url":"([^"]+)"', t):
    u = dec(x)
    if u not in vids: vids.append(u)
for x in re.findall(r'"display_url":"([^"]+)"', t):
    u = dec(x)
    if u not in imgs: imgs.append(u)
if not imgs:
    for x in re.findall(r'class="EmbeddedMediaImage"[^>]*src="([^"]+)"', raw):
        u = html.unescape(x)
        if u not in imgs: imgs.append(u)
lines = ["VIDEO|" + u for u in vids] if vids else ["IMG|" + u for u in imgs]
if not lines:
    sys.exit(1)
open(os.path.join(d, "plan.txt"), "w").write("\n".join(lines) + "\n")

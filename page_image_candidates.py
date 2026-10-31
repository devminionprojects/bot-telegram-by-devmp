# Diekstrak dari telegram-control-local-opensource.sh baris 6091-6140
# Fungsi shell asal: page_image_candidates()
# Dipanggil lewat: python - "$WEB_CACHE_DIR/index.tsv" "${DDG_VERIFY_MAX:-4}" <<'PY' 2>/dev/null
import sys, re, html, ipaddress
from urllib.parse import urljoin, urlparse
idx, mx = sys.argv[1], int(sys.argv[2])
def public(u):
    try:
        pu = urlparse(u); h = (pu.hostname or '').lower()
    except Exception:
        return False
    if pu.scheme not in ('http', 'https') or not h or h == 'localhost' or h.endswith(('.local', '.internal', '.lan', '.localdomain')):
        return False
    try:
        ip = ipaddress.ip_address(h)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return False
    except ValueError:
        pass
    return True
per_page = []
for line in open(idx, encoding='utf-8', errors='replace'):
    parts = line.rstrip('\n').split('\t')
    if len(parts) != 2: continue
    eff, path = parts
    try:
        t = open(path, 'rb').read(600000).decode('utf-8', 'replace')
    except Exception:
        continue
    cands = []
    for mt in re.finditer(r'<meta\s[^>]*>', t, re.I):
        tag = mt.group(0)
        k = re.search(r'(?:property|name)\s*=\s*["\']([^"\']+)["\']', tag, re.I)
        v = re.search(r'content\s*=\s*["\']([^"\']+)["\']', tag, re.I)
        if k and v and k.group(1).lower() in ('og:image', 'og:image:url', 'og:image:secure_url', 'twitter:image', 'twitter:image:src'):
            cands.append(v.group(1))
    lk = re.search(r'<link[^>]*rel\s*=\s*["\']image_src["\'][^>]*href\s*=\s*["\']([^"\']+)["\']', t, re.I)
    if lk: cands.append(lk.group(1))
    for jm in re.finditer(r'"image"\s*:\s*(?:\[\s*)?"([^"]+)"', t):
        cands.append(jm.group(1))
    out = []
    for c in cands:
        u = urljoin(eff, html.unescape(c).strip())
        if public(u) and u not in out and not re.search(r'(logo|favicon|sprite|placeholder|default[-_]?(image|og))', u, re.I):
            out.append(u)
    per_page.append((eff, out[:2]))
res = []; seen = set()
for rnd in range(2):
    for eff, imgs in per_page:
        if len(imgs) > rnd and imgs[rnd] not in seen and len(res) < mx:
            seen.add(imgs[rnd]); res.append((eff, imgs[rnd]))
for eff, u in res:
    print(eff + '\t' + u)

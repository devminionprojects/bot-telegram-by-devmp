# Diekstrak dari telegram-control-local-opensource.sh baris 5124-5162
# Fungsi shell asal: web_filter_new()
# Dipanggil lewat: code=$(cat <<'PYF'
import sys, re
from urllib.parse import urlparse
seen_file = sys.argv[1]
def norm(u):
    pu = urlparse(u.strip())
    h = re.sub(r'^www\.', '', (pu.netloc or '').lower())
    return h + (pu.path or '').rstrip('/') + (('?' + pu.query) if pu.query else '')
try:
    seen = set(l.rstrip('\n') for l in open(seen_file, encoding='utf-8'))
except Exception:
    seen = set()
n = len(seen)
lines = sys.stdin.read().split('\n')
i = 0
newkeys = []
out = []
while i < len(lines):
    m = re.match(r'^\d+\.(\s*\[[^\]]+\])?\s(.*)$', lines[i])
    if m and i + 1 < len(lines):
        label = m.group(1) or ''
        title = m.group(2)
        url = lines[i + 1].strip()
        j = i + 2
        snip = []
        while j < len(lines) and lines[j].startswith('   ') and not re.match(r'^\d+\.', lines[j]):
            snip.append(lines[j]); j += 1
        k = norm(url)
        if k and k not in seen:
            seen.add(k); newkeys.append(k); n += 1
            out.append('%d.%s %s' % (n, label, title))
            out.append('   ' + url)
            out.extend(snip)
        i = j
    else:
        i += 1
with open(seen_file, 'a', encoding='utf-8') as f:
    for k in newkeys:
        f.write(k + '\n')
print('\n'.join(out))

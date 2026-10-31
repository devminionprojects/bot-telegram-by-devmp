# Diekstrak dari telegram-control-local-opensource.sh baris 5000-5068
# Fungsi shell asal: ddg_search()
# Dipanggil lewat: res=$(DDG_MAX_RESULTS="$DDG_MAX_RESULTS" DDG_POOL="$DDG_POOL" DDG_TRUSTED_DOMAINS="$DDG_TRUSTED_DOMAINS" DDG_LOW_DOMAINS="$DDG_LOW_DOMAINS" DDG_PRIMAR
import sys, re, os, html as H
from urllib.parse import unquote, urlparse, parse_qs
mode = sys.argv[2]
def _lst(k):
    return [x.strip().lower() for x in os.environ.get(k, '').split(',') if x.strip()]
trusted = _lst('DDG_TRUSTED_DOMAINS')
low = _lst('DDG_LOW_DOMAINS')
primary = _lst('DDG_PRIMARY_DOMAINS')
try:
    maxr = max(1, min(200, int(os.environ.get('DDG_MAX_RESULTS', '5'))))
    pool = max(maxr, min(300, int(os.environ.get('DDG_POOL', '8'))))
except Exception:
    maxr, pool = 5, 8
try:
    raw = open(sys.argv[1], encoding='utf-8', errors='replace').read()
except Exception:
    raw = ''
def clean(t):
    return re.sub(r'\s+', ' ', H.unescape(re.sub(r'<[^>]+>', '', t))).strip()
marker = 'result__a' if mode == 'html' else 'result-link'
snip_re = (r'class=["\'][^"\']*result__snippet[^"\']*["\'][^>]*>(.*?)</a>' if mode == 'html'
           else r'class=["\'][^"\']*result-snippet[^"\']*["\'][^>]*>(.*?)</td>')
res = []
for m in re.finditer(r'<a\s([^>]*)>(.*?)</a>', raw, re.S):
    attrs = m.group(1)
    if marker not in attrs:
        continue
    hm = re.search(r'href=["\']([^"\']+)["\']', attrs)
    if not hm:
        continue
    href = H.unescape(hm.group(1))
    if href.startswith('//'):
        href = 'https:' + href
    qs = parse_qs(urlparse(href).query)
    url = unquote(qs['uddg'][0]) if 'uddg' in qs else href
    if 'duckduckgo.com/y.js' in url or 'ad_provider' in href:
        continue
    tail = raw[m.end():m.end() + 4000]
    sm = re.search(snip_re, tail, re.S)
    snip = clean(sm.group(1))[:300] if sm else ''
    res.append((clean(m.group(2))[:150], url, snip))
    if len(res) >= pool:
        break
if not res:
    print('__GAGAL__')
else:
    def host_of(u):
        h = urlparse(u).netloc.lower().split(':')[0]
        return re.sub(r'^www\.', '', h)
    def match(h, doms):
        return any(h == d or h.endswith('.' + d) for d in doms)
    ranked = []
    for idx, (t, u, sn) in enumerate(res):
        h = host_of(u)
        if match(h, low):
            tier, label = 3, ' [Kurang terpercaya]'
        elif match(h, primary):
            tier, label = 0, ' [Sumber resmi]'
        elif match(h, trusted):
            tier, label = 1, ' [Terpercaya]'
        else:
            tier, label = 2, ''
        ranked.append((tier, idx, t, u, sn, label))
    ranked.sort(key=lambda x: (x[0], x[1]))
    for i, (tier, idx, t, u, sn, label) in enumerate(ranked[:maxr], 1):
        print('%d.%s %s' % (i, label, t))
        print('   ' + u)
        if sn:
            print('   ' + sn)

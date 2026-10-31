# Diekstrak dari telegram-control-local-opensource.sh baris 5704-5905
# Fungsi shell asal: fetch_page_text()
# Dipanggil lewat: python - "$tmp" "$DDG_PAGE_CHARS" "$eff" "$query" <<'PY' 2>/dev/null
import sys, re, ipaddress
from html.parser import HTMLParser
from urllib.parse import urlparse
path, limit, eff = sys.argv[1], int(sys.argv[2]), sys.argv[3]
# tolak kalau setelah pengalihan mendarat di alamat lokal
try:
    h = (urlparse(eff).hostname or '').lower()
    if h == 'localhost' or h.endswith(('.local', '.internal', '.lan', '.localdomain')):
        sys.exit(0)
    try:
        ip = ipaddress.ip_address(h)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            sys.exit(0)
    except ValueError:
        pass
except Exception:
    pass
raw = open(path, 'rb').read()
m = re.search(rb'charset=["\']?([A-Za-z0-9_-]+)', raw[:4096])
enc = m.group(1).decode('ascii', 'ignore') if m else 'utf-8'
try:
    text = raw.decode(enc, errors='replace')
except LookupError:
    text = raw.decode('utf-8', errors='replace')

PRICE_RE = re.compile(r'(rp\.?\s?\d|\$\s?\d|usd\s?\d|\d\s?(%|kg|gr?|gram|ml|cm|mm|watt|w|volt|v|ah|mah|hz|jt|rb|ribu|juta|pcs|pack|hari|bulan|tahun|jam|menit)\b)', re.I)
def keep_short(line):
    # baris pendek tetap dipertahankan kalau berisi harga/ukuran/spesifikasi (contoh: "Rp256.000", "Berat: 200 g", "Garansi | 1 tahun")
    if len(line) < 3:
        return False
    if PRICE_RE.search(line):
        return True
    if re.search(r'\d', line) and (':' in line or '|' in line):
        return True
    if len(line) >= 6 and (':' in line or '|' in line):
        return True
    return False

class P(HTMLParser):
    SKIP = {'script','style','noscript','svg','nav','header','footer','aside','iframe','button','select','template','figure'}
    BLOCK = {'p','h1','h2','h3','h4','li','div','section','article','br','tr','blockquote','main','ul','ol','table','dt','dd','caption'}
    CELL = {'td','th'}
    HEAD = {'h1','h2','h3','h4'}
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip = 0; self.art = 0; self.main = 0
        self.buf = []; self.all = []; self.in_art = []; self.in_main = []
        self.title = ''; self.in_title = False; self.cur_head = False
    def flush(self):
        line = re.sub(r'\s+', ' ', ''.join(self.buf)).strip()
        line = re.sub(r'(\s*\|)+$', '', line).strip()
        self.buf = []
        if not line:
            return
        if len(line) >= 40 or (self.cur_head and len(line) >= 5) or keep_short(line):
            self.all.append(line)
            if self.art > 0: self.in_art.append(line)
            if self.main > 0: self.in_main.append(line)
    def handle_starttag(self, tag, attrs):
        if tag == 'title': self.in_title = True
        if tag in self.SKIP: self.skip += 1
        if tag in self.BLOCK or tag in self.HEAD:
            self.flush()
            self.cur_head = tag in self.HEAD
        if tag == 'article': self.art += 1
        if tag == 'main': self.main += 1
    def handle_endtag(self, tag):
        if tag == 'title': self.in_title = False
        if tag in self.BLOCK or tag in self.HEAD:
            self.flush()
            self.cur_head = False
        if tag in self.CELL and self.skip == 0:
            self.buf.append(' | ')
        if tag in self.SKIP and self.skip > 0: self.skip -= 1
        if tag == 'article' and self.art > 0: self.art -= 1
        if tag == 'main' and self.main > 0: self.main -= 1
    def handle_data(self, data):
        if self.in_title:
            self.title += data
        elif self.skip == 0:
            self.buf.append(data)

p = P()
try:
    p.feed(text); p.flush()
except Exception:
    pass
def total(l): return sum(len(x) for x in l)
chosen = p.in_art if total(p.in_art) >= 500 else (p.in_main if total(p.in_main) >= 500 else p.all)
if chosen is not p.all:
    # harga/spesifikasi pendek di luar blok artikel tetap ikut, urutan halaman dipertahankan
    cs = set(chosen)
    chosen = [l for l in p.all if l in cs or PRICE_RE.search(l)]
junk = ('baca juga','advertisement','iklan','cookie','privacy policy','kebijakan privasi','hak cipta','all rights reserved','berlangganan','subscribe','bagikan','share this','follow us','login','sign in')
seen = set(); out = []
for l in chosen:
    k = l.lower()
    if len(l) < 140 and any(j in k for j in junk):
        continue
    if k in seen:
        continue
    seen.add(k); out.append(l)
_q = sys.argv[4] if len(sys.argv) > 4 else ''
_stop = set('dan yang di ke dari untuk the of and for in on a an to terbaru hari ini sekarang apa siapa kapan berapa dengan pada adalah itu atau'.split())
qwords = list(dict.fromkeys(w for w in re.findall(r'[a-z0-9]+', _q.lower()) if (len(w) >= 3 or w.isdigit()) and w not in _stop))[:10]
body = '\n'.join(out)
if len(body) < 200:
    sys.exit(0)
if len(body) > limit:
    # Dibaca dari atas sampai bawah. Kalau melebihi batas: awal (35%) dan akhir (10%) selalu dipakai,
    # sisanya diisi baris tengah yang paling cocok dengan pertanyaan/harga/angka, urutan asli dipertahankan.
    head_b, tail_b = int(limit * 0.35), int(limit * 0.10)
    keep = set(); used = 0
    for i, l in enumerate(out):
        if used + len(l) + 1 > head_b: break
        keep.add(i); used += len(l) + 1
    tail_used = 0
    for i in range(len(out) - 1, -1, -1):
        if i in keep: break
        if tail_used + len(l := out[i]) + 1 > tail_b: break
        keep.add(i); tail_used += len(l) + 1
    used += tail_used
    def score(l):
        k = l.lower()
        sc = sum(2 for w in qwords if w in k)
        if PRICE_RE.search(l): sc += 2
        elif re.search(r'\d', l): sc += 1
        return sc
    mid = [(score(l), -i, i) for i, l in enumerate(out) if i not in keep]
    mid.sort(reverse=True)
    for sc, _, i in mid:
        if sc <= 0: break
        if used + len(out[i]) + 1 > limit: continue
        keep.add(i); used += len(out[i]) + 1
    body = '\n'.join(out[i] for i in sorted(keep))
    if len(body) > limit:
        body = body[:limit]
title = re.sub(r'\s+', ' ', p.title).strip()[:150]
# ---- metadata kualitas: tanggal terbit, penulis, HTTPS, kecocokan kata kunci ----
import datetime
query = sys.argv[4] if len(sys.argv) > 4 else ''
mm = {}
for mt in re.finditer(r'<meta\s[^>]*>', text[:300000], re.I):
    tag = mt.group(0)
    k = re.search(r'(?:property|name|itemprop|http-equiv)\s*=\s*["\']([^"\']+)["\']', tag, re.I)
    v = re.search(r'content\s*=\s*["\']([^"\']*)["\']', tag, re.I)
    if k and v:
        mm.setdefault(k.group(1).lower(), v.group(1).strip())
def find_date(keys, jsonkey):
    for k in keys:
        v = mm.get(k)
        if v and re.search(r'\d{4}', v):
            return v
    m = re.search(r'"' + jsonkey + r'"\s*:\s*"([^"]+)"', text)
    if m and re.search(r'\d{4}', m.group(1)):
        return m.group(1)
    return ''
pub = find_date(['article:published_time', 'og:article:published_time', 'datepublished', 'pubdate', 'publishdate', 'date', 'dc.date.issued', 'dc.date', 'sailthru.date', 'publish-date'], 'datePublished')
if not pub:
    tm = re.search(r'<time[^>]*datetime\s*=\s*["\']([^"\']+)["\']', text, re.I)
    if tm and re.search(r'\d{4}', tm.group(1)):
        pub = tm.group(1)
mod = find_date(['article:modified_time', 'og:updated_time', 'datemodified', 'last-modified'], 'dateModified')
def fmt(d):
    m = re.match(r'(\d{4})-(\d{2})-(\d{2})', d)
    if not m:
        return re.sub(r'\s+', ' ', d)[:40]
    try:
        days = (datetime.date.today() - datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))).days
        return '%s (%d hari lalu)' % (m.group(0), days) if days >= 0 else m.group(0)
    except Exception:
        return m.group(0)
author = mm.get('author') or mm.get('article:author') or mm.get('twitter:creator') or ''
if not author:
    am = re.search(r'"author"\s*:\s*(?:\[\s*)?\{[^}]*?"name"\s*:\s*"([^"]+)"', text)
    if am:
        author = am.group(1)
author = re.sub(r'\s+', ' ', author).strip()[:80]
stop = set('dan yang di ke dari untuk the of and for in on a an to terbaru hari ini sekarang apa siapa kapan berapa dengan pada adalah itu atau'.split())
words = [w for w in re.findall(r'[a-z0-9]+', query.lower()) if (len(w) >= 3 or w.isdigit()) and w not in stop]
words = list(dict.fromkeys(words))[:8]
hay = (title + ' ' + ' '.join(p.all)).lower()
hit = [w for w in words if w in hay]
if words:
    kw = 'kata kunci cocok %d dari %d' % (len(hit), len(words))
    miss = [w for w in words if w not in hit]
    if miss:
        kw += ' (tidak ada: ' + ', '.join(miss) + ')'
else:
    kw = 'kata kunci tidak dinilai'
sig = 'Sinyal: ' + ('HTTPS' if eff.lower().startswith('https') else 'TANPA HTTPS') + '; penulis/redaksi: ' + (author or 'tidak tercantum') + '; ' + kw
hdr = []
if title:
    hdr.append('Judul halaman: ' + title)
hdr.append('Tanggal terbit: ' + (fmt(pub) if pub else 'tidak tercantum'))
if mod and mod != pub:
    hdr.append('Terakhir diperbarui: ' + fmt(mod))
hdr.append(sig)
res = '\n'.join(hdr) + '\n' + body
# netralkan penanda [[...]] agar isi halaman tidak bisa memerintah bot
res = res.replace('[[', '[').replace(']]', ']')
print(res)

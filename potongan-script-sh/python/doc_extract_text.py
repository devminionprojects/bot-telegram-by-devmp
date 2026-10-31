# Diekstrak dari telegram-control-local-opensource.sh baris 5301-5546
# Fungsi shell asal: doc_extract_text()
# Dipanggil lewat: python - "$1" "$2" "$3" <<'PY' 2>/dev/null
import sys, os, re, zipfile, subprocess, shutil, zlib, ipaddress, html as H
from urllib.parse import urlparse, unquote
path, limit, eff = sys.argv[1], int(sys.argv[2]), sys.argv[3]
ctype = os.environ.get('DOC_CTYPE', '').lower()
# tolak kalau alamat akhir mengarah ke jaringan lokal (sama seperti pembaca halaman web)
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
fname = unquote(os.path.basename(urlparse(eff).path)) or 'dokumen'
ext = os.path.splitext(fname.lower())[1].lstrip('.')
head = open(path, 'rb').read(8)
kind = None; zf = None; names = set()
if head.startswith(b'%PDF'):
    kind = 'pdf'
elif head[:2] == b'PK':
    try:
        zf = zipfile.ZipFile(path); names = set(zf.namelist())
    except Exception:
        sys.exit(0)
    if 'word/document.xml' in names: kind = 'docx'
    elif 'xl/workbook.xml' in names: kind = 'xlsx'
    elif 'ppt/presentation.xml' in names: kind = 'pptx'
    elif 'content.xml' in names: kind = 'odf'
elif head.startswith(b'\xd0\xcf\x11\xe0'):
    kind = 'ole'
elif head.startswith(b'{\\rtf'):
    kind = 'rtf'
elif ext in ('csv', 'txt') or 'csv' in ctype or 'text' in ctype:
    kind = 'text'
if not kind:
    sys.exit(0)
labels = {'pdf': 'PDF', 'docx': 'Word', 'xlsx': 'Excel', 'pptx': 'PowerPoint', 'odf': 'OpenDocument', 'ole': 'Office lama', 'rtf': 'RTF', 'text': 'teks/CSV'}
pub = mod = ''; title = ''

def strip_xml(x):
    return H.unescape(re.sub(r'<[^>]+>', '', x))

def ooxml_meta():
    global pub, mod, title
    try:
        c = zf.read('docProps/core.xml').decode('utf-8', 'replace')
        m = re.search(r'<dcterms:created[^>]*>(\d{4}-\d{2}-\d{2})', c); pub = m.group(1) if m else ''
        m = re.search(r'<dcterms:modified[^>]*>(\d{4}-\d{2}-\d{2})', c); mod = m.group(1) if m else ''
        m = re.search(r'<dc:title[^>]*>([^<]+)</dc:title>', c); title = H.unescape(m.group(1)).strip() if m else ''
    except Exception:
        pass

def docx_text():
    ooxml_meta()
    x = zf.read('word/document.xml').decode('utf-8', 'replace')
    x = re.sub(r'</w:p>\s*</w:tc>', '</w:tc>', x)
    x = re.sub(r'</w:p>', '\n', x); x = re.sub(r'<w:tab\s*/>', '\t', x)
    x = re.sub(r'<w:(br|cr)\b[^>]*/>', '\n', x); x = re.sub(r'</w:tc>', '\t', x); x = re.sub(r'</w:tr>', '\n', x)
    return strip_xml(x)

def xlsx_text():
    import xml.etree.ElementTree as ET
    ooxml_meta()
    ns = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
    sst = []
    if 'xl/sharedStrings.xml' in names:
        for si in ET.fromstring(zf.read('xl/sharedStrings.xml')).iter(ns + 'si'):
            sst.append(''.join(t.text or '' for t in si.iter(ns + 't')))
    sheets = sorted([n for n in names if re.match(r'xl/worksheets/sheet\d+\.xml$', n)], key=lambda n: int(re.findall(r'\d+', n)[-1]))
    snames = []
    if 'xl/workbook.xml' in names:
        snames = [H.unescape(x) for x in re.findall(r'<sheet\b[^>]*?\bname="([^"]*)"', zf.read('xl/workbook.xml').decode('utf-8', 'replace'))]
    out = []
    for i, n in enumerate(sheets, 1):
        out.append('[Lembar %d%s]' % (i, (': ' + snames[i - 1]) if i - 1 < len(snames) and snames[i - 1] else ''))
        for row in ET.fromstring(zf.read(n)).iter(ns + 'row'):
            # kolom dihitung dari alamat sel (A1, B1, ...) supaya sel kosong di tengah baris tidak menggeser kolom
            cells = {}; mx = -1
            for c in row.iter(ns + 'c'):
                v = c.find(ns + 'v'); t = c.get('t')
                mm = re.match(r'([A-Za-z]+)', c.get('r') or '')
                if mm:
                    ci = 0
                    for ch in mm.group(1).upper():
                        ci = ci * 26 + (ord(ch) - 64)
                    ci -= 1
                else:
                    ci = mx + 1
                if t == 's' and v is not None and (v.text or '').isdigit() and int(v.text) < len(sst):
                    val = sst[int(v.text)]
                elif t == 'inlineStr':
                    val = ''.join(x.text or '' for x in c.iter(ns + 't'))
                elif v is not None and v.text is not None:
                    val = v.text
                else:
                    val = ''
                cells[ci] = val.replace('\t', ' ').replace('\n', ' ')
                if ci > mx: mx = ci
            if any(cells.values()):
                out.append('\t'.join(cells.get(k, '') for k in range(mx + 1)).rstrip('\t'))
    return '\n'.join(out)

def pptx_text():
    ooxml_meta()
    slides = sorted([n for n in names if re.match(r'ppt/slides/slide\d+\.xml$', n)], key=lambda n: int(re.findall(r'\d+', n)[-1]))
    out = []
    for i, n in enumerate(slides, 1):
        x = zf.read(n).decode('utf-8', 'replace')
        out.append('[Slide %d]\n%s' % (i, strip_xml(re.sub(r'</a:p>', '\n', x)).strip()))
    return '\n\n'.join(out)

def odf_text():
    x = zf.read('content.xml').decode('utf-8', 'replace')
    x = re.sub(r'</text:(p|h)>', '\n', x); x = re.sub(r'</table:table-cell>', '\t', x)
    x = re.sub(r'</table:table-row>', '\n', x); x = re.sub(r'<text:(tab|line-break)\s*/>', ' ', x)
    return strip_xml(x)

def rtf_drop_groups(s):
    for key in (r'{\*', r'{\fonttbl', r'{\colortbl', r'{\stylesheet', r'{\info', r'{\pict', r'{\header', r'{\footer'):
        while True:
            i = s.find(key)
            if i < 0: break
            d = 0; j = i
            while j < len(s):
                if s[j] == '{': d += 1
                elif s[j] == '}':
                    d -= 1
                    if d == 0: break
                j += 1
            s = s[:i] + s[j + 1:]
    return s

def rtf_text():
    s = rtf_drop_groups(open(path, 'rb').read().decode('latin-1'))
    s = re.sub(r"\\'([0-9a-fA-F]{2})", lambda m: bytes([int(m.group(1), 16)]).decode('cp1252', 'replace'), s)
    s = re.sub(r'\\u(-?\d+)\??', lambda m: chr(int(m.group(1)) % 65536), s)
    s = re.sub(r'\\(par|line)\b ?', '\n', s); s = re.sub(r'\\tab\b ?', '\t', s)
    s = re.sub(r'\\[a-zA-Z]+-?\d* ?', '', s)
    return re.sub(r'[{}]', '', s)

def ole_text():
    if 'excel' in ctype or ext == 'xls': cmds = [['xls2csv', path], ['catdoc', path]]
    elif 'powerpoint' in ctype or ext == 'ppt': cmds = [['catppt', path]]
    else: cmds = [['antiword', path], ['catdoc', path]]
    for c in cmds:
        if shutil.which(c[0]):
            try:
                r = subprocess.run(c, capture_output=True)
                if r.returncode == 0 and r.stdout.strip():
                    return r.stdout.decode('utf-8', 'replace')
            except Exception:
                pass
    return ''

def sane(t):
    t = t.strip()
    if len(t) < 20: return False
    ok = sum(1 for ch in t if ch.isprintable() or ch.isspace())
    letters = sum(1 for ch in t if ch.isalpha() or ch.isspace())
    return ok / len(t) >= 0.95 and letters / len(t) >= 0.6

def pdf_unescape(b):
    out = bytearray(); i = 0
    while i < len(b):
        c = b[i:i + 1]
        if c == b'\\' and i + 1 < len(b):
            n = b[i + 1:i + 2]; i += 2
            if n in b'nrtbf': out += {b'n': b'\n', b'r': b'\n', b't': b'\t', b'b': b'', b'f': b''}[n]
            elif n.isdigit():
                d = n
                while len(d) < 3 and i < len(b) and b[i:i + 1].isdigit(): d += b[i:i + 1]; i += 1
                out.append(int(d, 8) & 255)
            else: out += n
        else:
            out += c; i += 1
    return bytes(out).decode('latin-1')

def pdf_simple():
    # pembaca PDF sederhana (cadangan terakhir): hanya untuk PDF dengan teks biasa, hasilnya diperiksa kewajarannya
    data = open(path, 'rb').read(); parts = []
    for m in re.finditer(rb'stream\r?\n(.*?)\r?\n?endstream', data, re.S):
        s = m.group(1)
        try: s = zlib.decompressobj().decompress(s)
        except Exception: pass
        for t in re.finditer(rb'\[(.*?)\]\s*TJ|\((.*?)(?<!\\)\)\s*Tj', s, re.S):
            if t.group(1) is not None:
                parts.append(''.join(pdf_unescape(x) for x in re.findall(rb'\((.*?)(?<!\\)\)', t.group(1), re.S)))
            else:
                parts.append(pdf_unescape(t.group(2)))
    t = '\n'.join(parts)
    return t if sane(t) else ''

def pdf_text():
    global pub, mod, title
    if shutil.which('pdfinfo'):
        try:
            info = subprocess.run(['pdfinfo', '-isodates', path], capture_output=True).stdout.decode('utf-8', 'replace')
            m = re.search(r'^CreationDate:\s*(\d{4}-\d{2}-\d{2})', info, re.M); pub = m.group(1) if m else ''
            m = re.search(r'^ModDate:\s*(\d{4}-\d{2}-\d{2})', info, re.M); mod = m.group(1) if m else ''
            m = re.search(r'^Title:\s*(.+)$', info, re.M); title = m.group(1).strip() if m else ''
        except Exception:
            pass
    if shutil.which('pdftotext'):
        try:
            r = subprocess.run(['pdftotext', '-layout', '-enc', 'UTF-8', path, '-'], capture_output=True)
            t = r.stdout.decode('utf-8', 'replace').replace('\f', '\n\n')
            if len(t.strip()) >= 20: return t
        except Exception:
            pass
    try:
        import pypdf
        rd = pypdf.PdfReader(path)
        if rd.is_encrypted:
            rd.decrypt('')
        t = '\n\n'.join((pg.extract_text() or '') for pg in rd.pages)
        if len(t.strip()) >= 20: return t
    except Exception:
        pass
    return pdf_simple()

try:
    if kind == 'pdf': text = pdf_text()
    elif kind == 'docx': text = docx_text()
    elif kind == 'xlsx': text = xlsx_text()
    elif kind == 'pptx': text = pptx_text()
    elif kind == 'odf': text = odf_text()
    elif kind == 'rtf': text = rtf_text()
    elif kind == 'ole': text = ole_text()
    else: text = open(path, 'rb').read().decode('utf-8', 'replace')
except Exception:
    text = ''
text = re.sub(r'[ \t]+\n', '\n', text); text = re.sub(r'\n{3,}', '\n\n', text).strip()
if len(text) < 20:
    sys.exit(0)
text = text[:limit]
hdr = ['Judul halaman: %s (dokumen %s)' % (title or fname, labels[kind]),
       'Tanggal terbit: ' + (pub or 'tidak tercantum')]
if mod and mod != pub:
    hdr.append('Terakhir diperbarui: ' + mod)
hdr.append('Sinyal: ' + ('HTTPS' if eff.lower().startswith('https') else 'TANPA HTTPS') + '; dokumen %s (bukan halaman web); penulis/redaksi: tidak tercantum; kata kunci tidak dinilai' % labels[kind])
res = '\n'.join(hdr) + '\n' + text
print(res.replace('[[', '[').replace(']]', ']'))

# Diekstrak dari telegram-control-local-opensource.sh baris 2616-2640
# Fungsi shell asal: pdf_scanned_pages()
# Dipanggil lewat: python - "$f" <<'PY' 2>/dev/null
import re, subprocess, sys
path = sys.argv[1]
foot = re.compile(r'ditandatangani secara elektronik|sertifikat elektronik|Balai Besar Sertifikasi|Powered by TCPDF|Dipindai dengan|CamScanner', re.I)
try:
    info = subprocess.run(['pdfinfo', path], capture_output=True).stdout.decode('utf-8', 'replace')
    m = re.search(r'^Pages:\s*(\d+)', info, re.M)
    n = int(m.group(1)) if m else 0
    r = subprocess.run(['pdftotext', '-enc', 'UTF-8', path, '-'], capture_output=True)
except Exception:
    sys.exit(0)
if r.returncode != 0:
    sys.exit(0)   # terkunci/rusak: tidak bisa dinilai
txt = r.stdout.decode('utf-8', 'replace')
if txt.endswith('\f'):
    txt = txt[:-1]
pages = txt.split('\f')
if n <= 0:
    n = len(pages)
pages += [''] * (n - len(pages))
out = []
for i in range(n):
    t = ''.join(l for l in pages[i].splitlines() if not foot.search(l))
    if len(re.sub(r'\s+', '', t)) < 80:
        out.append(str(i + 1))
print(' '.join(out))

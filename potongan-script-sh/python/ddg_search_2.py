# Diekstrak dari telegram-control-local-opensource.sh baris 5074-5094
# Fungsi shell asal: ddg_search()
# Dipanggil lewat: python - "$tmp" "$attempt" > "$DDG_NEXT_FILE" 2>/dev/null <<'PYN'
import sys, re, html as H
raw = open(sys.argv[1], encoding='utf-8', errors='replace').read()
out = []
for fm in re.finditer(r'<form\b[^>]*>(.*?)</form>', raw, re.S | re.I):
    body = fm.group(1)
    if not re.search(r'<input[^>]*type=["\']submit["\'][^>]*value=["\']\s*Next', body, re.I) and \
       not re.search(r'<input[^>]*value=["\']\s*Next[^>]*type=["\']submit["\']', body, re.I):
        continue
    for im in re.finditer(r'<input\b([^>]*)>', body, re.I):
        a = im.group(1)
        if not re.search(r'type=["\']hidden["\']', a, re.I):
            continue
        nm = re.search(r'name=["\']([^"\']+)["\']', a)
        vl = re.search(r'value=["\']([^"\']*)["\']', a)
        if nm:
            out.append((nm.group(1), H.unescape(vl.group(1)) if vl else ''))
    break
if out:
    print(sys.argv[2])
    for k, v in out:
        print(k + '\t' + v)

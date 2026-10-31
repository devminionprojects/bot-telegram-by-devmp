# Diekstrak dari telegram-control-local-opensource.sh baris 5579-5611
# Fungsi shell asal: big_download_confirm()
# Dipanggil lewat: decision=$(RESP="$resp" CHAT="$chat" BASE="$base" python - <<'PY' 2>/dev/null
import json, os
yes = {'ya','iya','y','yes','ok','oke','okey','lanjut','gas','sip','unduh','ya unduh','ya lanjut','iya lanjut'}
no = {'batal','tidak','gak','ga','nggak','enggak','no','n','jangan','skip','lewati','cancel','/batal','stop'}
try:
    data = json.loads(os.environ.get('RESP', '') or '{}')
except Exception:
    data = {}
chat = os.environ.get('CHAT', '')
try:
    base = int(os.environ.get('BASE', '-1'))
except Exception:
    base = -1
for u in data.get('result', []):
    uid = u.get('update_id', 0)
    if uid <= base:
        continue
    cb = u.get('callback_query') or {}
    if cb:
        if str(((cb.get('message') or {}).get('chat') or {}).get('id', '')) == chat:
            print('lain|%s' % uid)
            break
        continue
    msg = u.get('message') or {}
    if str((msg.get('chat') or {}).get('id', '')) != chat:
        continue
    text = (msg.get('text') or '').strip().lower()
    if text in yes:
        print('ya|%s' % uid)
    elif text in no:
        print('batal|%s' % uid)
    else:
        print('lain|%s' % uid)
    break

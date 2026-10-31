# Diekstrak dari telegram-control-local-opensource.sh baris 8791-8820
# Fungsi shell asal: spotify_send_page()
# Dipanggil lewat: body=$(OUT="$(spotify_results_file)" PAGE="$page" PS="$SPOTIFY_PAGE_SIZE" CHAT="$CURRENT_CHAT_ID" MID="$mid" python - <<'PY' 2>/dev/null
import os, json, math
E = os.environ
d = json.load(open(E["OUT"], encoding="utf-8"))
items = d["items"]
ps = max(1, int(E.get("PS", "5")))
pages = max(1, math.ceil(len(items) / ps))
p = min(max(int(E["PAGE"]), 1), pages)
a, b = (p - 1) * ps, min(p * ps, len(items))
def dur(ms):
    s = int(ms) // 1000
    return "%d:%02d" % (s // 60, s % 60) if s else ""
lines = ["🎧 Spotify · \"%s\"" % d["q"][:60],
         "Hasil %d-%d dari %d (halaman %d/%d)" % (a + 1, b, len(items), p, pages), ""]
for i in range(a, b):
    it = items[i]
    t = "%d. %s — %s" % (i + 1, it["title"][:50], it["artist"][:40])
    if dur(it["ms"]): t += " (%s)" % dur(it["ms"])
    lines.append(t)
lines += ["", "Ketuk nomor lagu untuk memutarnya."]
kb = [[{"text": str(i + 1), "callback_data": "spo_t_%d" % i} for i in range(a, b)]]
nav = []
if p > 1: nav.append({"text": "◀️", "callback_data": "spo_p_%d" % (p - 1)})
nav.append({"text": "%d/%d" % (p, pages), "callback_data": "spo_p_%d" % p})
if p < pages: nav.append({"text": "▶️", "callback_data": "spo_p_%d" % (p + 1)})
kb.append(nav)
cid = E["CHAT"]
body = {"chat_id": int(cid) if cid.lstrip("-").isdigit() else cid,
        "text": "\n".join(lines), "reply_markup": {"inline_keyboard": kb}}
if E.get("MID"): body["message_id"] = int(E["MID"])
print(json.dumps(body, ensure_ascii=False))

# Diekstrak dari telegram-control-local-opensource.sh baris 1076-1083
# Fungsi shell asal: tt_send_desc()
# Dipanggil lewat: body=$(D="$d" CHAT="$CURRENT_CHAT_ID" RID="$rid" python3 - <<'PYD' 2>/dev/null
import os, json, html
E = os.environ
t = open(E["D"] + "/desc.txt", encoding="utf-8").read().strip()[:3800]
cid = E["CHAT"]
d = {"chat_id": int(cid) if cid.lstrip("-").isdigit() else cid, "parse_mode": "HTML",
     "text": "📝 <b>Deskripsi video</b>\n<blockquote expandable>" + html.escape(t) + "</blockquote>"}
if E.get("RID"): d["reply_parameters"] = {"message_id": int(E["RID"]), "allow_sending_without_reply": True}
print(json.dumps(d))

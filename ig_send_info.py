# Diekstrak dari telegram-control-local-opensource.sh baris 1365-1379
# Fungsi shell asal: ig_send_info()
# Dipanggil lewat: mapfile -t rich_list < <(D="$d" WHO="$who" BOT="$bot" CHAT="$CURRENT_CHAT_ID" RID="$rid" python3 - <<'PYI' 2>/dev/null
import os, json
E = os.environ
st = json.load(open(E["D"] + "/stats.json"))
rows = [("\U0001F464", "Akun", st["akun"]), ("\U0001F3F7\uFE0F", "Tipe", st["tipe"]), ("\u2764\uFE0F", "Suka", st["suka"]),
        ("\U0001F4AC", "Komentar", st["komentar"])]
if st.get("video"):
    rows += [("\U0001F441\uFE0F", "Views", st["views"]), ("\u23F1\uFE0F", "Durasi", st["dur"])]
foot = "Diminta oleh %s \u00B7 via %s" % (E["WHO"] or "kamu", ("@" + E["BOT"]) if E["BOT"] else "bot")
c = lambda x: str(x).replace("|", "/").replace("`", "'").replace("\n", " ")
md = "**Informasi Instagram**\n\n| Info | Detail |\n|---|---|\n" + "".join("| %s %s | %s |\n" % (i, l, c(v)) for i, l, v in rows) + "\n" + foot
cid = E["CHAT"]
d = {"chat_id": int(cid) if cid.lstrip("-").isdigit() else cid, "rich_message": {"markdown": md}}
if E.get("RID"):
    d["reply_parameters"] = {"message_id": int(E["RID"]), "allow_sending_without_reply": True}
print(json.dumps(d))

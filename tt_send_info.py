# Diekstrak dari telegram-control-local-opensource.sh baris 975-1006
# Fungsi shell asal: tt_send_info()
# Dipanggil lewat: mapfile -t rich_list < <(D="$d" WHO="$who" BOT="$bot" CHAT="$CURRENT_CHAT_ID" RID="$rid" python3 - <<'PYI' 2>/dev/null
import os, json, html
E = os.environ
st = json.load(open(E["D"] + "/stats.json"))
desc = ""
try: desc = open(E["D"] + "/desc.txt", encoding="utf-8").read().strip()
except Exception: pass
rows = [("⏱️", "Durasi", st["dur"]), ("👁️", "Views", st["views"]), ("💬", "Komentar", st["comments"]),
        ("🔁", "Share", st["shares"]), ("🏷️", "Tipe", st["tipe"])]
foot = "Diminta oleh %s · via %s" % (E["WHO"] or "kamu", ("@" + E["BOT"]) if E["BOT"] else "bot")
cid = E["CHAT"]
base = {"chat_id": int(cid) if cid.lstrip("-").isdigit() else cid}
if E.get("RID"):
    base["reply_parameters"] = {"message_id": int(E["RID"]), "allow_sending_without_reply": True}
def out(rm):
    d = dict(base); d["rich_message"] = rm; print(json.dumps(d))
# varian 1: HTML + <details> (buka selengkapnya) berisi deskripsi asli
h = ("<h3>Informasi Video</h3><table><tr><th>Info</th><th>Detail</th></tr>"
     + "".join("<tr><td>%s %s</td><td>%s</td></tr>" % (i, l, html.escape(str(v))) for i, l, v in rows) + "</table>")
if desc:
    h += "<details><summary>Buka untuk lihat deskripsi video</summary><p>" + html.escape(desc).replace("\n", "<br/>") + "</p></details>"
h += "<p>" + html.escape(foot) + "</p>"
out({"html": h})
# varian 2: Markdown tabel + <details>
c = lambda x: str(x).replace("|", "/").replace("`", "'").replace("\n", " ")
md = "**Informasi Video**\n\n| Info | Detail |\n|---|---|\n" + "".join("| %s %s | %s |\n" % (i, l, c(v)) for i, l, v in rows)
if desc:
    md += "\n<details><summary>Buka untuk lihat deskripsi video</summary>\n\n" + desc + "\n\n</details>\n"
md += "\n" + foot
out({"markdown": md})
# varian 3: tabel saja (tanpa bagian buka selengkapnya)
md2 = "**Informasi Video**\n\n| Info | Detail |\n|---|---|\n" + "".join("| %s %s | %s |\n" % (i, l, c(v)) for i, l, v in rows) + "\n" + foot
out({"markdown": md2})

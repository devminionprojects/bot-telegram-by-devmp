# Diekstrak dari telegram-control-local-opensource.sh baris 1033-1056
# Fungsi shell asal: tt_send_combined()
# Dipanggil lewat: mapfile -t rich_list < <(D="$d" WHO="$who" BOT="$bot" python3 - <<'PYC' 2>/dev/null
import os, json, html
E = os.environ
st = json.load(open(E["D"] + "/stats.json"))
desc = ""
try: desc = open(E["D"] + "/desc.txt", encoding="utf-8").read().strip()
except Exception: pass
rows = [("⏱️", "Durasi", st["dur"]), ("👁️", "Views", st["views"]), ("💬", "Komentar", st["comments"]),
        ("🔁", "Share", st["shares"]), ("🏷️", "Tipe", st["tipe"])]
foot = "Diminta oleh %s · via %s" % (E["WHO"] or "kamu", ("@" + E["BOT"]) if E["BOT"] else "bot")
media = [{"id": "vid", "media": {"type": "video", "media": "attach://vid", "supports_streaming": True,
                                "duration": int(st.get("secs") or 0)}}]
h = "<video src=\"tg://video?id=vid\"></video><h3>Informasi Video</h3><table><tr><th>Info</th><th>Detail</th></tr>"
h += "".join("<tr><td>%s %s</td><td>%s</td></tr>" % (i, l, html.escape(str(v))) for i, l, v in rows) + "</table>"
if desc:
    h += "<details><summary>Buka untuk lihat deskripsi video</summary><p>" + html.escape(desc).replace("\n", "<br/>") + "</p></details>"
h += "<p>" + html.escape(foot) + "</p>"
print(json.dumps({"html": h, "media": media}))
c = lambda x: str(x).replace("|", "/").replace("`", "'").replace("\n", " ")
md = "![](tg://video?id=vid)\n\n**Informasi Video**\n\n| Info | Detail |\n|---|---|\n"
md += "".join("| %s %s | %s |\n" % (i, l, c(v)) for i, l, v in rows)
if desc:
    md += "\n<details><summary>Buka untuk lihat deskripsi video</summary>\n\n" + desc + "\n\n</details>\n"
md += "\n" + foot
print(json.dumps({"markdown": md, "media": media}))

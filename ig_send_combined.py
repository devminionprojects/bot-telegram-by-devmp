# Diekstrak dari telegram-control-local-opensource.sh baris 1402-1435
# Fungsi shell asal: ig_send_combined()
# Dipanggil lewat: mapfile -t rich_list < <(D="$d" WHO="$who" BOT="$bot" KIND="$kind" python3 - <<'PYC' 2>/dev/null
import os, json, html
E = os.environ
st = json.load(open(E["D"] + "/stats.json"))
desc = ""
try: desc = open(E["D"] + "/desc.txt", encoding="utf-8").read().strip()
except Exception: pass
rows = [("\U0001F464", "Akun", st["akun"]), ("\U0001F3F7\uFE0F", "Tipe", st["tipe"]), ("\u2764\uFE0F", "Suka", st["suka"]),
        ("\U0001F4AC", "Komentar", st["komentar"])]
if st.get("video"):
    rows += [("\U0001F441\uFE0F", "Views", st["views"]), ("\u23F1\uFE0F", "Durasi", st["dur"])]
rows = [r for r in rows if str(r[2]) not in ("-", "")]
foot = "Diminta oleh %s \u00B7 via %s" % (E["WHO"] or "kamu", ("@" + E["BOT"]) if E["BOT"] else "bot")
k = E["KIND"]
m = {"type": k, "media": "attach://vid"}
if k == "video":
    m["supports_streaming"] = True
    m["duration"] = int(st.get("secs") or 0)
media = [{"id": "vid", "media": m}]
h = '<%s src="tg://%s?id=vid"></%s>' % ("video" if k == "video" else "img", k, "video" if k == "video" else "img")
if k == "photo":
    h = '<img src="tg://photo?id=vid"/>'
h += "<h3>Informasi Instagram</h3><table><tr><th>Info</th><th>Detail</th></tr>"
h += "".join("<tr><td>%s %s</td><td>%s</td></tr>" % (i, l, html.escape(str(v))) for i, l, v in rows) + "</table>"
if desc:
    h += "<details><summary>Buka untuk lihat deskripsi</summary><p>" + html.escape(desc).replace("\n", "<br/>") + "</p></details>"
h += "<p>" + html.escape(foot) + "</p>"
print(json.dumps({"html": h, "media": media}))
c = lambda x: str(x).replace("|", "/").replace("`", "'").replace("\n", " ")
md = "![](tg://%s?id=vid)\n\n**Informasi Instagram**\n\n| Info | Detail |\n|---|---|\n" % k
md += "".join("| %s %s | %s |\n" % (i, l, c(v)) for i, l, v in rows)
if desc:
    md += "\n<details><summary>Buka untuk lihat deskripsi</summary>\n\n" + desc + "\n\n</details>\n"
md += "\n" + foot
print(json.dumps({"markdown": md, "media": media}))

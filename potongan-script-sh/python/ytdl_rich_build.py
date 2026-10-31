# Diekstrak dari telegram-control-local-opensource.sh baris 1699-1752
# Fungsi shell asal: ytdl_rich_build()
# Dipanggil lewat: KIND="$1" D="$2" WHO="$3" BOT="$4" THUMB="$5" RID="$6" CHAT="$CURRENT_CHAT_ID" DESC_MAX="${YTDL_DESC_MAX:-2500}" python3 - <<'PYR_YT' 2>/dev/null
import os, json, html
E = os.environ
st = json.load(open(E["D"] + "/stats.json"))
desc = ""
try: desc = open(E["D"] + "/desc.txt", encoding="utf-8").read().strip()
except Exception: pass
try: mx = int(E.get("DESC_MAX") or 2500)
except Exception: mx = 2500
desc_r = desc if (mx <= 0 or len(desc) <= mx) else desc[:mx].rstrip() + "\u2026"
rows = [r for r in st["rows"] if str(r[2]) not in ("", "-")]
foot = "Diminta oleh %s \u00B7 via %s" % (E.get("WHO") or "kamu", ("@" + E["BOT"]) if E.get("BOT") else "bot")
kind = E["KIND"]
secs = int(st.get("secs") or 0)
title = st.get("title") or ""
HEAD = "Informasi YouTube"
c = lambda x: str(x).replace("|", "/").replace("`", "'").replace("\n", " ")
e = lambda x: html.escape(str(x))
def table_html():
    return ("<h3>" + HEAD + "</h3><table><tr><th>Info</th><th>Detail</th></tr>"
            + "".join("<tr><td>%s %s</td><td>%s</td></tr>" % (i, l, e(v)) for i, l, v in rows) + "</table>")
def desc_html():
    if not desc_r: return ""
    return "<details><summary>Buka untuk lihat deskripsi video</summary><p>" + e(desc_r).replace("\n", "<br/>") + "</p></details>"
def table_md():
    return ("**" + HEAD + "**\n\n| Info | Detail |\n|---|---|\n"
            + "".join("| %s %s | %s |\n" % (i, l, c(v)) for i, l, v in rows))
def desc_md():
    if not desc_r: return ""
    return "\n<details><summary>Buka untuk lihat deskripsi video</summary>\n\n" + desc_r + "\n\n</details>\n"
def wrap(rm):
    if kind != "info": return rm
    cid = E["CHAT"]
    d = {"chat_id": int(cid) if cid.lstrip("-").isdigit() else cid, "rich_message": rm}
    if E.get("RID"): d["reply_parameters"] = {"message_id": int(E["RID"]), "allow_sending_without_reply": True}
    return d
def out(tag, rm): print(tag + "|" + json.dumps(wrap(rm)))
if kind == "video":
    vmedia = [{"id": "vid", "media": {"type": "video", "media": "attach://vid", "supports_streaming": True, "duration": secs}}]
    out("V", {"html": '<video src="tg://video?id=vid"></video>' + table_html() + desc_html() + "<p>" + e(foot) + "</p>", "media": vmedia})
    out("V", {"markdown": "![](tg://video?id=vid)\n\n" + table_md() + desc_md() + "\n" + foot, "media": vmedia})
elif kind == "audio":
    amedia = {"id": "song", "media": {"type": "audio", "media": "attach://song", "title": title, "performer": st.get("chan") or "", "duration": secs}}
    if E.get("THUMB"):
        cover = {"id": "cover", "media": {"type": "photo", "media": E["THUMB"]}}
        out("A", {"html": '<figure><img src="tg://photo?id=cover"/><figcaption>\U0001F3B5 ' + e(title) + "</figcaption></figure>"
                  + table_html() + desc_html() + '<audio src="tg://audio?id=song"></audio><p>' + e(foot) + "</p>", "media": [cover, amedia]})
        out("A", {"markdown": '![](tg://photo?id=cover "\U0001F3B5 ' + c(title).replace('"', "'") + '")\n\n' + table_md() + desc_md()
                  + "\n![](tg://audio?id=song)\n\n" + foot, "media": [cover, amedia]})
    out("N", {"html": table_html() + desc_html() + '<audio src="tg://audio?id=song"></audio><p>' + e(foot) + "</p>", "media": [amedia]})
    out("N", {"markdown": table_md() + desc_md() + "\n![](tg://audio?id=song)\n\n" + foot, "media": [amedia]})
else:
    out("F", {"html": table_html() + desc_html() + "<p>" + e(foot) + "</p>"})
    out("F", {"markdown": table_md() + desc_md() + "\n" + foot})
    out("N", {"markdown": table_md() + "\n" + foot})

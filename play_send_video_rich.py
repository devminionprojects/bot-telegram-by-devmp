# Diekstrak dari telegram-control-local-opensource.sh baris 628-675
# Fungsi shell asal: play_send_video_rich()
# Dipanggil lewat: mapfile -t rich_list < <(TITLE="$title" CHAN="$chan" VIEWS="$views_txt" DUR="$dur_txt" AGO="$ago_txt" WHO="${who:-kamu}" SECS="$secs" WITH_AUDIO="${af
import os, json, html
E = os.environ
c = lambda k: E[k].replace("|", "/").replace("`", "'").replace("\n", " ").replace('"', "'")
h = lambda k: html.escape(E[k].replace("\n", " "))
secs = int(E["SECS"] or 0)
def vmedia(kind):
    m = {"type": kind, "media": "attach://vid", "duration": secs}
    if kind == "video": m["supports_streaming"] = True
    return {"id": "vid", "media": m}
amedia = {"id": "song", "media": {"type": "audio", "media": "attach://song", "title": E["TITLE"], "performer": E["CHAN"], "duration": secs}}
rows = [("\U0001F464", "Channel", "CHAN"), ("\U0001F441\uFE0F", "Views", "VIEWS"), ("\u23F1\uFE0F", "Durasi", "DUR"), ("\U0001F4C5", "Upload", "AGO")]

def md(audio, tag):
    s = '![](tg://' + tag + '?id=vid "\U0001F3B5 ' + c("TITLE") + '")\n\n' if tag else ""
    s += "**Informasi Lagu**\n\n| Info | Detail |\n|---|---|\n"
    s += "".join("| %s %s | %s |\n" % (i, l, c(k)) for i, l, k in rows)
    s += "\n"
    if audio:
        s += "![](tg://audio?id=song)\n\n"
    return s + "Diminta oleh " + c("WHO") + " \u00B7 via YouTube"

def ht(audio, video=True, tag="video", auto=False):
    s = '<figure><video src="tg://' + tag + '?id=vid"' + (" autoplay loop muted playsinline" if auto else "") + '></video><figcaption>\U0001F3B5 ' + h("TITLE") + "</figcaption></figure>" if video else ""
    s += "<h3>Informasi Lagu</h3><table><tr><th>Info</th><th>Detail</th></tr>"
    s += "".join("<tr><td>%s %s</td><td>%s</td></tr>" % (i, l, h(k)) for i, l, k in rows) + "</table>"
    if audio:
        s += '<audio src="tg://audio?id=song"></audio>'
    return s + "<p>Diminta oleh " + h("WHO") + " \u00B7 via YouTube</p>"

def out(k, d): print(k + "|" + json.dumps(d))
if E.get("ANIM_DONE"):
    # video sudah terkirim sebagai animasi: pesan ini hanya tabel + pemutar audio
    out("AU", {"markdown": md(True, None), "media": [amedia]})
    out("AU", {"html": ht(True, False), "media": [amedia]})
elif E.get("WITH_AUDIO"):
    if E.get("SILENT"):
        # AA = animasi (jalan sendiri) + audio; AV = video tanpa suara + audio
        out("AA", {"html": ht(True, True, "animation", True), "media": [vmedia("animation"), amedia]})
        out("AV", {"html": ht(True, True, "video", True), "media": [vmedia("video"), amedia]})
        out("AA", {"markdown": md(True, "animation"), "media": [vmedia("animation"), amedia]})
        out("AV", {"markdown": md(True, "video"), "media": [vmedia("video"), amedia]})
    # AO = video BERSUARA + audio (ketuk video = suara dari video, atau tombol ungu = suara saja)
    out("AO", {"html": ht(True, True, "video", True), "media": [vmedia("video"), amedia]})
    out("AO", {"markdown": md(True, "video"), "media": [vmedia("video"), amedia]})
    out("AO", {"html": ht(True), "media": [vmedia("video"), amedia]})
if not E.get("ANIM_DONE"):
    out("V", {"markdown": md(False, "video"), "media": [vmedia("video")]})
    out("V", {"html": ht(False), "media": [vmedia("video")]})

# Diekstrak dari telegram-control-local-opensource.sh baris 135-144
# Fungsi shell asal: yt_full()
# Dipanggil lewat: python - "$d" "$url" "${ck[@]}" <<'PY' > "$d/meta.txt" 2>/dev/null
import sys, json, subprocess
d, url, *ck = sys.argv[1:]
r = subprocess.run(["yt-dlp","--skip-download","--no-playlist","-J",*ck,url],
                   capture_output=True, text=True, timeout=120)
j = json.loads(r.stdout)
print("Judul:", j.get("title")); print("Kanal:", j.get("channel"))
print("Tanggal:", j.get("upload_date")); print("Durasi (detik):", j.get("duration"))
for c in j.get("chapters") or []:
    print(f'Bab {int(c["start_time"])}s: {c["title"]}')
print("Deskripsi:\n", j.get("description") or "")

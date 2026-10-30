# 🤖 Ai Agent Tools — Telegram Control untuk Termux

> Bot Telegram serba-bisa yang berjalan di **HP Android (Termux)** dalam **satu file Bash**.
> Dikendalikan lewat chat Telegram: AI chat (Gemini), NAS pribadi, pencarian internet, unduh YouTube / TikTok / Instagram, pemutar lagu, kompres file, pengingat, monitoring server, dan kendali Termux dari jarak jauh.

**Versi script:** `Lokal 792` · **Bahasa:** Bash + Python (embedded) · **Platform:** Android + Termux
**Dibuat oleh:** Moh Hilmi Mulia R. · **Tim:** MP (Minions Project)

---

## 📑 Daftar Isi

1. [Ringkasan Fitur](#-ringkasan-fitur)
2. [Cara Kerja](#-cara-kerja)
3. [Persyaratan](#-persyaratan)
4. [Instalasi](#-instalasi)
5. [Konfigurasi](#-konfigurasi)
6. [Menjalankan Bot](#-menjalankan-bot)
7. [Daftar Perintah](#-daftar-perintah)
8. [Penjelasan Fitur Lengkap](#-penjelasan-fitur-lengkap)
9. [Fitur Khusus Pemilik](#-fitur-khusus-pemilik)
10. [Batas Ukuran, Durasi, dan Waktu](#-batas-ukuran-durasi-dan-waktu)
11. [File yang Dibuat Bot](#-file-yang-dibuat-bot)
12. [Keamanan](#-keamanan)
13. [Pemecahan Masalah](#-pemecahan-masalah)
14. [Struktur Script](#-struktur-script)
15. [Kredit](#-kredit)

---

## ✨ Ringkasan Fitur

| Kategori | Fitur |
|---|---|
| 🤖 **AI** | Chat dengan Google Gemini, ingatan percakapan per chat, komentar foto/video, baca dokumen (PDF, Word, Excel, PowerPoint, CSV, teks, dll.), OCR PDF hasil scan |
| 🔎 **Internet** | Pencarian DuckDuckGo otomatis, membaca isi halaman sumber, prioritas sumber resmi/terpercaya, verifikasi foto barang, link Tokopedia/Shopee untuk harga |
| 💾 **NAS pribadi** | Simpan foto/video/dokumen per tanggal, per pengguna (terpisah), cari, ambil, hapus, indeks isi file |
| 🎬 **YouTube** | `yt` (ringkasan AI), `ytraw` (transkrip), `ytdl` (unduh MP4/MP3), `play` (putar lagu) |
| 🎵 **Musik** | `play` (video + pemutar audio), `spotify` (hasil bertombol + Mini App kartu, playlist, lirik) |
| 📥 **Downloader** | TikTok tanpa watermark, Instagram (post/reel/carousel/story), YouTube MP4/MP3 |
| 🗜️ **Kompres** | Kompres video/foto/PDF/Office/audio ke ukuran target |
| ⏰ **Produktivitas** | Pengingat & timer (diulang sampai dibalas), catatan cepat, info terjadwal dari internet |
| 🎨 **Hiburan** | Stiker teks, game Tic Tac Toe (Mini App) lawan bot atau teman |
| 🛡️ **Monitoring** | Laporan harian, peringatan ESP32 / Nginx / Cloudflare tunnel / SSH / baterai / disk |
| 👑 **Admin (pemilik)** | Kelola pengguna, blokir ID, update script via Telegram (rollback otomatis), kendali Termux, foto kamera HP, lihat/hapus NAS semua ID, riwayat pengunjung ke Excel |
| 🌞 **Dashboard** | Ganti mode web PLTS / Maintenance dan update dashboard `.html` |

---

## 🧠 Cara Kerja

Script berjalan sebagai **loop polling** (default tiap 3 detik) ke API Telegram, memeriksa pesan baru, lalu menjalankan perintah yang sesuai.

```mermaid
flowchart LR
    U[Pengguna Telegram] -->|pesan / file / link| T[Telegram Bot API<br/>server lokal 127.0.0.1:8081]
    T -->|getUpdates| B[Script Bash<br/>Termux]
    B -->|prompt + riwayat| G[Google Gemini API]
    B -->|search| D[DuckDuckGo]
    B -->|unduh| Y[yt-dlp / tikwm API]
    B --> N[(NAS lokal<br/>nas_storage / nas_users)]
    B --> M[Mini App server<br/>port 8090]
    B -->|monitor| E[ESP32 :8080 · Nginx · Cloudflared · SSH]
    B -->|sendMessage / sendVideo / ...| T
```

Hal penting:

- **Whitelist ID.** Hanya `OWNER_CHAT_ID` dan ID tambahan yang terdaftar yang dilayani. ID lain hanya bisa `/start` dan membuka Menu Fitur; sisanya "terkunci".
- **Server Bot API lokal.** Script dirancang untuk [`telegram-bot-api`](https://github.com/tdlib/telegram-bot-api) lokal sehingga batas unggah/unduh file besar (hingga 2 GB per file) tidak dibatasi oleh server Telegram biasa.
- **AI memakai penanda khusus.** Gemini menulis penanda seperti `[[INGATKAN: …]]`, `[[CARI_FILE: …]]`, `[[CATAT: …]]`, `CARI_WEB` yang dikenali script lalu dijalankan (lihat [Penanda AI](#penanda-ai-internal)).
- **Satu file.** Seluruh fitur (termasuk server Mini App Python) ada di satu file `.sh`; server Mini App ditulis ulang otomatis tiap bot dijalankan.

---

## 📋 Persyaratan

### Perangkat & aplikasi

- HP Android dengan **[Termux](https://termux.dev)** (disarankan dari F-Droid / GitHub release)
- **Termux:API** (aplikasi + paket `termux-api`) — hanya untuk perintah `foto`, status baterai, dan info WiFi
- Koneksi internet stabil dan **bot Telegram** dari [@BotFather](https://t.me/BotFather)
- **API key Google Gemini** dari [aistudio.google.com](https://aistudio.google.com)

### Paket Termux

```bash
pkg update && pkg upgrade -y
pkg install -y bash curl python ffmpeg ghostscript poppler python-pillow procps openssh termux-api
```

### Paket Python

```bash
pip install -U yt-dlp openpyxl pypdf
```

| Paket | Dipakai untuk |
|---|---|
| `yt-dlp` | `yt`, `ytraw`, `ytdl`, `play`, `ig`, cadangan `tt` |
| `ffmpeg` / `ffprobe` | Gabung video+audio, MP3, kompres video/foto/audio |
| `ghostscript` | Kompres PDF |
| `poppler` (`pdftotext`) | Baca teks PDF |
| `python-pillow` | Stiker teks, kompres foto & gambar dalam dokumen Office |
| `openpyxl` | File Excel riwayat pengunjung (kalau tidak ada, dibuat CSV) |
| `pypdf` | Pemrosesan PDF |
| `termux-api` | Foto kamera, baterai, WiFi |
| `procps` | Uptime (`/proc/uptime` sering diblokir Android) |
| `openssh` | Pemeriksaan `sshd` |

### Komponen opsional

| Komponen | Fungsi |
|---|---|
| **telegram-bot-api** (server lokal) | Hilangkan batas ukuran file; alamat default `http://127.0.0.1:8081` |
| **Nginx** | Menyajikan dashboard web dari `~/www` |
| **cloudflared** | Tunnel Cloudflare untuk dashboard dan Mini App (HTTPS) |
| **ESP32** | Sumber data PLTS, dicek lewat `http://localhost:8080/data` (JSON berisi kunci `"v"`) |
| **`~/set-mode.sh`** | Script pengganti mode web (`plts` / `maintenance`) |
| **Kredensial Spotify** (opsional) | Pencarian lagu via Spotify; tanpa ini dipakai iTunes |

---

## 🚀 Instalasi

```bash
# 1. Unduh repo
git clone https://github.com/<username>/<repo>.git
cd <repo>

# 2. Beri izin eksekusi
chmod +x telegram-control-local.sh

# 3. Edit konfigurasi (token, API key, ID pemilik, dll.)
nano telegram-control-local.sh

# 4. Jalankan
./telegram-control-local.sh
```

> Nama file bisa disesuaikan. Baris pertama script memakai shebang Termux:
> `#!/data/data/com.termux/files/usr/bin/bash`

### Langkah ringkas dari nol

1. Buat bot di **@BotFather** → salin **token**.
2. Cari **chat ID** akunmu (mis. lewat @userinfobot) → jadikan `OWNER_CHAT_ID`.
3. Buat **API key Gemini** di Google AI Studio.
4. (Disarankan) Jalankan **telegram-bot-api** lokal di port `8081` dengan mode `--local`.
5. Isi ketiga nilai tersebut di bagian atas script.
6. Jalankan script, lalu kirim `/start` ke bot kamu.

---

## ⚙️ Konfigurasi

Semua pengaturan ada di **bagian atas script** (baris 1–130 dan di awal tiap blok fitur). Beri nilai `0` pada banyak batas berarti **tanpa batas**.

### Wajib diisi

| Variabel | Keterangan |
|---|---|
| `TELEGRAM_TOKEN` | Token bot dari BotFather |
| `OWNER_CHAT_ID` | ID Telegram pemilik (selalu diizinkan, satu-satunya yang bisa menambah pengguna) |
| `GEMINI_API_KEY` | API key Gemini dari aistudio.google.com |
| `TELEGRAM_API` | Alamat server Bot API (`http://127.0.0.1:8081` untuk lokal; `https://api.telegram.org` untuk server resmi) |

### Akses & pengguna

| Variabel | Bawaan | Keterangan |
|---|---|---|
| `EXTRA_IDS_FILE` | `~/.telegram_extra_ids` | Daftar ID tambahan (1 ID per baris) |
| `MAX_EXTRA_IDS` | `0` | Batas jumlah ID tambahan (`0` = tanpa batas) |
| `LOCK_WA_NUMBER` / `LOCK_WA_DISPLAY` | – | Nomor WhatsApp pemilik untuk tombol "minta buka kunci" |
| `LOCK_REPLY_COOLDOWN` | `10` | Jeda balasan "terkunci" ke ID yang sama (detik) |
| `BLOCKED_FILE` | `~/.telegram_blocked` | Daftar ID yang diblokir |
| `BLOCK_REPLY_COOLDOWN` | `60` | Jeda balasan peringatan blokir |
| `VISITORS_NOTIFY` | `1` | Catat & kabari pemilik tiap ada pengunjung `/start` baru |
| `DEVELOPER_CHAT_ID` | – | ID yang dikenali AI sebagai developer (sambutan khusus) |
| `POLL_INTERVAL` | `3` | Jeda polling (detik) |

### Tampilan

| Variabel | Bawaan | Keterangan |
|---|---|---|
| `BANNER_PHOTO` | `~/banner.jpg` | Foto banner pada `/start` |
| `BANNER_VIDEO` | `~/banner.mp4` | Video banner (bila ada, foto diabaikan) |
| `WELCOME_WIDTH_PAD` | `36` | Pelebar kotak "Informasi Bot" |

### NAS & file

| Variabel | Bawaan | Keterangan |
|---|---|---|
| `NAS_SEND_MAX` | `0` | Maks file yang dikirim saat pencarian (`0` = semua) |
| `NAS_FILE_MAX_BYTES` | `0` | Batas ukuran file kirim. Server resmi: `50000000` |
| `NAS_PHOTO_MAX_BYTES` | `0` | Foto di atas ukuran ini dikirim sebagai dokumen |
| `NAS_SEND_TIMEOUT` | `0` | Batas waktu kirim satu file (detik) |
| `DELETE_CONFIRM_TTL` | `120` | Waktu menjawab "ya" sebelum permintaan hapus hangus |

### Dokumen & AI

| Variabel | Bawaan | Keterangan |
|---|---|---|
| `DOC_READ_CHARS` | `1000000` | Batas karakter isi dokumen yang dibaca |
| `DOC_HISTORY_CHARS` | `0` | Karakter dokumen yang disimpan di ingatan (`0` = utuh) |
| `DOC_OCR_PDF` | `1` | OCR halaman PDF hasil scan lewat AI |
| `DOC_OCR_BATCH_PAGES` | `10` | Halaman scan per satu panggilan AI |
| `DOC_OCR_MAX_MB` | `1024` | Ukuran PDF maksimal yang dibaca |
| `DOC_OCR_INLINE_MAX_MB` | `14` | PDF ≤ ini dikirim langsung; lebih besar via Files API Gemini |
| `YT_GEMINI_MODEL` | `gemini-2.5-flash` | Model untuk baca video langsung (cadangan `yt`) |

### Pencarian web

| Variabel | Bawaan | Keterangan |
|---|---|---|
| `WEB_SEARCH_MAX` | `0` | Maks pencarian lanjutan per pertanyaan |
| `DDG_DOH_URL` | `https://cloudflare-dns.com/dns-query` | DNS-over-HTTPS untuk menembus blokir DNS ISP |
| `DDG_MAX_RESULTS` | `5` | Jumlah hasil ke AI (1–5) |
| `DDG_POOL` | `8` | Hasil teratas yang jadi kandidat |
| `DDG_READ_PAGES` | `5` | Halaman teratas yang dibuka |
| `DDG_PAGE_CHARS` / `DDG_TOTAL_CHARS` | `1000000` | Batas karakter per halaman / total |
| `BIG_DL_LIMIT` | `100000000` | Halaman > 100 MB ditanyakan dulu |
| `BIG_DL_WAIT` | `300` | Menunggu jawaban ya/batal (detik) |
| `BIG_DL_STALL` | `120` | Hentikan unduhan yang macet total (detik) |
| `PAGE_TYPE_PRECHECK` | `1` | Cek jenis berkas sebelum unduh |
| `WEB_WANT_MAX` | `100` | Batas wajar jumlah yang diminta ("20 berita") |
| `WEB_MAX_SERP_PAGES` | `0` | Maks halaman hasil DuckDuckGo |
| `DDG_VERIFY_MAX` | `4` | Gambar yang dibandingkan dengan foto kiriman |
| `DDG_TRUSTED_DOMAINS` | daftar | Sumber terpercaya (ditandai & didahulukan) |
| `DDG_PRIMARY_DOMAINS` | daftar | Sumber resmi/primer |
| `DDG_LOW_DOMAINS` | daftar | Sumber kurang terpercaya |

### Pengingat, catatan, info terjadwal

| Variabel | Bawaan | Keterangan |
|---|---|---|
| `REMINDER_REPEAT_INTERVAL` | `60` | Jeda ulang pengingat yang belum dibalas (detik) |
| `REMINDER_REPEAT_MAX` | `0` | Maks ulang (`0` = sampai dibalas) |
| `SCHEDINFO_MAX` | `0` | Maks info terjadwal per chat |
| `NOTES_FILE` | `~/.telegram_notes` | Lokasi catatan |

### Monitoring & laporan

| Variabel | Bawaan | Keterangan |
|---|---|---|
| `DAILY_DEFAULT_TIME` | `07:00` | Jam laporan harian |
| `HEALTH_CHECK_INTERVAL` | `10` | Jeda pemeriksaan kesehatan (detik) |
| `HEALTH_BATT_LOW` | `10` | Peringatan baterai ≤ persen ini |
| `BATT_SPAM_INTERVAL` | `30` | Jeda pesan baterai rendah (`0` = tidak diulang) |
| `HEALTH_DISK_HIGH` | `90` | Peringatan disk ≥ persen ini |
| `HEALTH_SSH_CHECK` | `1` | Cek `sshd` |
| `LOG_VERBOSE` | `1` | Tampilkan log di layar |
| `LOG_FILE` | `~/telegram-control.log` | File log (otomatis dikosongkan bila > 1 MB) |

### YouTube

| Variabel | Bawaan | Keterangan |
|---|---|---|
| `YT_COOKIES` | `~/yt-cookies.txt` | Cookie Netscape (opsional; untuk video dibatasi umur / dianggap bot) |
| `YT_MAX_CHARS` | `0` | Batas karakter transkrip ke AI |
| `YT_DETAIL_CHUNK` | `24000` | Ukuran potongan transkrip mode `lengkap` |
| `YT_RAW_TIMESTAMP` | `1` | Awali baris transkrip dengan `[mm:ss]` |
| `YT_RAW_KIRIM_PESAN` | `1` | Kirim transkrip sebagai pesan chat |
| `YT_RAW_KIRIM_FILE` | `1` | Kirim juga file `.txt` |
| `YT_RAW_TERJEMAH` | `1` | Terjemahkan subtitle non-Indonesia dengan AI |
| `YT_RAW_BATCH` | `100` | Baris subtitle per sekali terjemah |
| `YTDL_HEIGHT` | `720` | Kualitas video bawaan (`0` = terbaik) |
| `YTDL_MP3_QUALITY` | `0` | Kualitas MP3 (0 terbaik … 10 terkecil) |
| `YTDL_MAX_SECS` | `0` | Batas durasi unduhan (`0` = tanpa batas) |
| `YTDL_MAX_MB` | `0` | Batas ukuran unduhan (`49` untuk server resmi) |
| `YTDL_PLAYLIST_MAX` | `5` | Jumlah video pertama pada playlist |
| `YTDL_DESC_MAX` | `2500` | Maks karakter deskripsi di pesan gabungan |

### Putar lagu (`play`)

| Variabel | Bawaan | Keterangan |
|---|---|---|
| `PLAY_SEARCH_N` | `10` | Jumlah hasil pencarian yang dibandingkan jumlah penontonnya |
| `PLAY_VIDEO` | `1` | `1` = kirim video + pemutar audio |
| `PLAY_VIDEO_HEIGHT` | `360` | Tinggi video (piksel) |
| `PLAY_VIDEO_MAX_SECS` | `900` | Lebih panjang dari ini → thumbnail + MP3 |
| `PLAY_MAX_MB` | `0` | Batas ukuran (`49` untuk server resmi) |
| `PLAY_VIDEO_AUDIO` | `1` | Sertakan pemutar audio pada pesan video |
| `PLAY_VIDEO_AUTOPLAY` | `2` | `2` = satu pesan video bersuara + pemutar audio; `1` = dua pesan; `0` = video biasa |

### TikTok, Instagram, Kompres, Stiker

| Variabel | Bawaan | Keterangan |
|---|---|---|
| `TT_API` | `https://www.tikwm.com/api/` | Sumber utama TikTok |
| `TT_HD` | `1` | Ambil HD jika ada |
| `IG_COOKIES` | `~/ig-cookies.txt` | Cookie Instagram (wajib untuk story/highlight/akun privat) |
| `COMPRESS_MARGIN` | `95` | Bidik 95% dari target ukuran |
| `STICKER_MAX_CHARS` | `300` | Batas panjang teks stiker |
| `STICKER_FONT` | kosong | Path font `.ttf` bold sendiri (opsional) |

### Spotify & Mini App

| Variabel | Bawaan | Keterangan |
|---|---|---|
| `SPOTIFY_SOURCE` | `auto` | Sumber pencarian (Spotify bila ada kredensial, jika tidak iTunes) |
| `SPOTIFY_CLIENT_ID` / `SPOTIFY_CLIENT_SECRET` | kosong | Dari developer.spotify.com/dashboard (opsional) |
| `SPOTIFY_PAGE_SIZE` | `5` | Lagu per halaman |
| `SPOTIFY_COUNTRY` | `ID` | Negara untuk iTunes |
| `SPOTIFY_WEBAPP_URL` | – | URL **HTTPS** Mini App (kosong = Mini App mati; juga dibutuhkan game `ttt`) |
| `SPOTIFY_APP_PORT` | `8090` | Port lokal server Mini App (arahkan tunnel/nginx ke sini) |
| `SPOTIFY_VIDEO_KEEP` | `8` | Jumlah video terakhir yang disimpan di cache |

### Update script & Termux

| Variabel | Bawaan | Keterangan |
|---|---|---|
| `UPDATE_BACKUP_DIR` | `~/telegram-control-backup` | Folder cadangan script lama |
| `UPDATE_BACKUP_KEEP` | `5` | Jumlah cadangan disimpan |
| `UPDATE_WATCHDOG_SECONDS` | `120` | Batas waktu script baru melapor aktif sebelum rollback |
| `UPDATE_MAX_BYTES` | `3000000` | Ukuran maksimal file script yang diterima |
| `TERMUX_CONFIRM_TTL` | `120` | Waktu membalas "ya" sebelum perintah hangus |
| `TERMUX_CMD_TIMEOUT` | `120` | Batas waktu perintah berjalan |
| `TERMUX_SAFETY` | `0` | `1` = aktifkan daftar larangan perintah berbahaya |
| `FOTO_BOLEH_SEMUA` | `0` | `1` = semua ID terdaftar boleh memakai `foto` (**hati-hati**) |
| `FOTO_HAPUS_DETIK` | `60` | Foto kamera dihapus dari chat setelah sekian detik |

---

## ▶️ Menjalankan Bot

### Langsung di Termux

```bash
./telegram-control-local.sh
```

### Di latar belakang (agar tidak mati saat sesi ditutup)

```bash
# Cegah Android mematikan Termux
termux-wake-lock

# Jalankan dengan tmux
pkg install -y tmux
tmux new -s bot './telegram-control-local.sh'
# lepas: Ctrl+B lalu D   |   kembali: tmux attach -t bot
```

### Melihat log

```bash
tail -f ~/telegram-control.log
```

### Jalan otomatis saat Termux dibuka

Tambahkan di `~/.bashrc` atau pakai **Termux:Boot**:

```bash
pgrep -f telegram-control-local.sh >/dev/null || tmux new -d -s bot '~/telegram-control-local.sh'
```

---

## 💬 Daftar Perintah

Banyak perintah juga bisa diketik dengan garis miring (`/yt`, `/play`, dst.) dan sebagian dipahami lewat **bahasa biasa** di chat.

### Untuk semua pengguna terdaftar

| Perintah | Fungsi | Contoh |
|---|---|---|
| `/start` | Sambutan, banner, tombol Menu Fitur | `/start` |
| *(teks biasa)* | Tanya apa saja ke AI (ingat obrolan & file) | `jelaskan apa itu inverter` |
| *(kirim foto/video)* | Dikomentari AI (caption = pertanyaan) | foto + `ini barang apa?` |
| *(kirim dokumen)* | Dibaca lengkap, jawab sesuai caption | PDF + `ringkas dokumen ini` |
| `lupakan` / `reset ai` | Hapus ingatan AI | `lupakan` |
| `web <kata kunci>` | Paksa cari di internet | `web harga emas hari ini` |
| `carikan 20 berita ...` | Minta jumlah hasil tertentu | `carikan 20 berita bola hari ini` |
| `cari lagi` / `update` / `cek ulang` | Paksa data baru | `cari lagi` |
| `nas` | Ringkasan file per tanggal | `nas` |
| `nas <tanggal>` | Daftar bernomor | `nas 03-10-2026` |
| `nas <tanggal> <no>` | Ambil 1 file | `nas 03-10-2026 1` / `nas 03-10-2026 foto 2` |
| `<tanggal>` | Ambil semua file hari itu | `21-09-2026` |
| `cari <kata> [bulan-tahun] [kirim]` | Cari file di NAS | `cari foto panel 10-2026 kirim` |
| `hapus <jenis> <tanggal> <no>` | Hapus file NAS milikmu (konfirmasi `ya`) | `hapus foto 03-10-2026 5` |
| `hapus <tanggal>` | Hapus semua file di tanggal itu | `hapus 20-11-2026` |
| `yt <link> [mode/pertanyaan]` | Ringkasan video YouTube oleh AI | `yt https://youtu.be/xxxx poin` |
| `ytraw <link>` | Transkrip YouTube + file `.txt` | `ytraw https://youtu.be/xxxx` |
| `ytdl <link>` | Unduh video MP4 | `ytdl https://youtu.be/xxxx` |
| `ytdl mp3 <link>` / `ytmp3 <link>` | Unduh audio MP3 | `ytmp3 https://youtu.be/xxxx` |
| `ytdl <kualitas> <link>` | Pilih kualitas | `ytdl 1080 https://youtu.be/xxxx` |
| `tt <link>` / `tt mp3 <link>` | Unduh TikTok tanpa watermark | `tt https://vt.tiktok.com/xxxx` |
| `ig <link>` / `ig mp3 <link>` | Unduh Instagram | `ig https://www.instagram.com/reel/xxxx` |
| `play <judul>` | Cari & putar lagu dari YouTube | `play sadrah` |
| `spotify <judul>` | Pencarian lagu bertombol | `spotify merry christmas` |
| `spotify` | Buka Mini App Spotify | `spotify` |
| *(kirim file + caption)* `compres <ukuran>` | Kompres ke ukuran target | caption `compres 60mb` |
| `ingatkan <waktu> <isi>` | Buat pengingat/timer | `ingatkan aku 30 menit lagi minum obat` |
| `pengingat` / `batal pengingat <no>` | Daftar / batalkan | `batal pengingat 1` |
| `spam ya` / `spam tidak` / `spam tanya` | Atur kebiasaan ulang pengingat | `spam ya` |
| `buatin info ...` | Info internet terjadwal | `setiap hari jam 6.00 carikan 20 berita` |
| `info terjadwal` / `batal info <no>` | Daftar / batalkan | `batal info 1` |
| `catat <isi>` | Simpan catatan | `catat password wifi: abc123` |
| `catatan [kata]` / `hapus catatan <no>` | Lihat, cari, hapus | `catatan wifi` |
| `stiker <teks>` | Teks → stiker putih | `stiker SELAMAT PAGI` |
| `ttt` | Game Tic Tac Toe (Mini App) | `ttt` |
| `waktu` | Cek jam server & status laporan | `waktu` |

### Khusus pemilik

| Perintah | Fungsi |
|---|---|
| `plts` / `maintenance` | Ganti mode web (via `~/set-mode.sh`) |
| *(kirim `.html`)* | Ganti dashboard, lalu `plts`/`maintenance` untuk menerapkan |
| `status` | RAM, baterai, suhu, WiFi, uptime, ESP32, Nginx, tunnel |
| `monitor` / `monitor on` / `monitor off` | Cek / hidupkan / matikan peringatan otomatis |
| `laporan` / `laporan on` / `laporan off` / `laporan jam 06:30` | Laporan harian |
| `id <id>` / `hapusid <id>` / `listid` | Kelola pengguna tambahan |
| `blok <id>` / `bukablok <id>` / `listblok` | Blokir / buka blokir |
| `pengunjung` | Riwayat `/start` + file Excel |
| `backup` | File cadangan bot (pengingat, dll.) |
| `foto` / `foto belakang` | Foto kamera HP server |
| `/termux <permintaan>` | AI menyusun perintah shell (jalan setelah `ya`) |
| `/cmd <perintah>` | Jalankan perintah persis seperti ditulis (jalan setelah `ya`) |
| *(kirim `.sh` + caption)* `update script` | Update script bot dengan rollback otomatis |
| `nas all id [tanggal]` | Lihat NAS semua ID |
| `nas id <id> [tanggal]` | Kirim file NAS milik ID lain |
| `hapus nas id <id> ...` | Hapus file NAS ID lain (permanen, konfirmasi `ya`) |

---

## 📖 Penjelasan Fitur Lengkap

### 🤖 AI Chat + Ingatan

- Memakai **Google Gemini**. Riwayat percakapan disimpan per chat (`~/.gemini_history_<chat_id>.json`).
- AI ingat obrolan, file yang dikirim (nama, tanggal tersimpan, isi/ringkasan), dan hasil tombol.
- Gaya bicara santai & humoris; tidak memakai simbol markdown mentah di Telegram.
- Catatan pengguna ikut dikirim ke Gemini setiap chat (jangan simpan yang terlalu rahasia).
- `lupakan` / `reset ai` menghapus ingatan.
- AI mengenali tanggal relatif (hari ini, besok, lusa, bulan lalu) dari kalender 15 hari yang diberikan script.

### 🖼️ Foto, Video & Dokumen

- **Foto/video** dikomentari AI; caption dijawab terlebih dulu. Jika ada yang janggal, AI memberi kritik dan saran.
- **Dokumen yang dibaca penuh:** PDF, Word (`docx/doc`), Excel (`xlsx/xls`), PowerPoint (`pptx/ppt`), OpenDocument (`odt/ods/odp`), RTF, CSV/TSV, teks biasa, dan file teks lain (json, log, kode).
- **PDF scan** dibaca lewat OCR AI (per kloter halaman) lalu digabung ke teks.
- Tidak terbaca: file terkunci/berpassword, arsip, audio, video (bot jujur menyatakan tidak terbaca).
- Dokumen tidak dicari di internet kecuali caption menyebut internet/web/google.
- Ringkasan dokumen masuk ke ingatan chat dan indeks pencarian NAS.

### 🔎 Pencarian Internet

- Pertanyaan berita, harga, skor, dll. di chat biasa otomatis dicari lewat **DuckDuckGo** (`web <kata>` untuk memaksa).
- Sebelum mencari, AI memeriksa riwayat chat; info cepat berubah (skor, harga, kurs, cuaca, berita) hanya dipakai dari riwayat bila dari hari ini.
- **Urutan sumber:** resmi/primer → terpercaya → lainnya (ditandai). Bot membuka dan membaca halaman sumber **dari atas sampai bawah**, mengecek tanggal terbit, penulis, HTTPS dan kecocokan isi, lalu **membandingkan antar sumber**. Fakta disebut pasti jika minimal 2 situs berbeda sepakat.
- **Jumlah tertentu** (`carikan 20 berita ...`): bot terus membaca sampai jumlah terpenuhi, lanjut ke halaman hasil berikutnya dan variasi kata kunci.
- **Harga barang:** menyertakan link pencarian **Tokopedia** dan **Shopee**.
- **Pencarian dari foto:** bandingkan foto dengan gambar hasil pencarian; harga hanya disebut bila barangnya **sama**, jika hanya **mirip** ditandai produk mirip.
- DNS-over-HTTPS (`DDG_DOH_URL`) untuk melewati pemblokiran DNS dari ISP.

### 💾 NAS Pribadi

- Kirim foto/video/dokumen → otomatis tersimpan **per tanggal**.
- **NAS tiap ID terpisah**: pemilik di `~/nas_storage`, pengguna lain di `~/nas_users/<id>`.
- Ambil, cari, lihat daftar, dan hapus lewat perintah atau bahasa biasa.
- Kirim ulang file dengan **format asli** (foto tetap foto, video tetap video); jika ditolak Telegram, dikirim sebagai dokumen.
- Pengiriman banyak file satu per satu (jeda 1 detik) dengan laporan sukses/gagal di akhir.
- Menghapus pesan di Telegram **tidak** menghapus file di server — gunakan perintah `hapus`.
- Penghapusan **permanen** selalu meminta konfirmasi `ya` (batal: `batal`, hangus dalam 2 menit).
- Indeks pencarian: `~/.nas_index` (tanggal | nama file | caption | ringkasan isi).

### 🎬 YouTube

#### `yt` — Ringkasan oleh AI

| Perintah | Hasil |
|---|---|
| `yt <link>` | Ringkasan selengkap mungkin, urut per bagian |
| `yt <link> ringkas` | Padat, tiap bagian 1–3 kalimat |
| `yt <link> poin` | Semua poin penting dalam daftar |
| `yt <link> lengkap` / `detail` | Dijabarkan selengkap mungkin; video panjang dikirim per bagian |
| `yt <link> <pertanyaan>` | Menjawab pertanyaan **hanya** dari isi video |

Cara kerja: `yt-dlp` mengambil judul, kanal, tanggal, durasi, deskripsi, bab, dan transkrip subtitle (buatan pemilik didahulukan, lalu otomatis; Indonesia/Inggris). Jika tidak ada subtitle, **Gemini membaca videonya langsung** (hanya video publik).

#### `ytraw` — Transkrip

| Perintah | Hasil |
|---|---|
| `ytraw <link>` (juga `yt mentah`, `yt raw`) | Seluruh transkrip, pesan chat + file `.txt`, tiap baris diawali `[mm:ss]` |
| `ytraw asli <link>` | Bahasa asli, tanpa terjemahan |
| `ytraw id <link>` / `ytraw en <link>` | Paksa subtitle bahasa tertentu dari YouTube |

Subtitle non-Indonesia otomatis diterjemahkan AI baris demi baris (tanpa meringkas). Video 1 jam bisa menjadi belasan sampai dua puluhan pesan; set `YT_RAW_KIRIM_PESAN=0` bila hanya ingin file `.txt`.

#### `ytdl` — Unduh video/audio

| Perintah | Hasil |
|---|---|
| `ytdl <link>` | MP4 H.264 + AAC (bawaan 720p) |
| `ytdl <kualitas> <link>` | 144, 240, 360, 480, 720, 1080, 1440, 2160, `4k`, `terbaik` |
| `ytdl mp3 <link>` / `ytmp3 <link>` / `yt mp3 <link>` | MP3 + cover + pemutar audio |

Alias: `/ytdl`, `/ytmp3`, `/ytmp4`, `ytmp4`, `yt dl`, `yt download`, `yt unduh`.

- Mendukung video biasa, Shorts, `youtu.be`, `music.youtube.com`, embed, live yang sudah selesai, dan **playlist** (`YTDL_PLAYLIST_MAX` video pertama, satu per satu).
- Link kanal tidak didukung; siaran langsung/premiere yang belum selesai ditolak.
- Hasil: video/cover + tabel **Informasi YouTube** (judul, channel, tipe & kualitas, durasi, views, suka, komentar, upload, ukuran) + deskripsi yang bisa dibuka + "Diminta oleh … via @bot" dalam **satu pesan**; bila ditolak Telegram, file dikirim dulu lalu tabel terpisah.
- **File hasil unduhan bersifat sementara** (folder `mktemp`, dihapus setelah terkirim).
- Tanpa `ffmpeg`, hanya format yang sudah menyatu yang bisa diunduh dan audio dikirim sebagai `m4a`.

> Link YouTube yang dikirim **tanpa** `yt` / `ytraw` / `ytdl` tidak dibaca dan tidak diunduh otomatis.

### 🎵 Putar Lagu (`play`)

- Mengambil `PLAY_SEARCH_N` (10) hasil teratas pencarian YouTube dan memilih yang **penontonnya terbanyak**.
- Mengirim **video (360p) + tabel Informasi Lagu (channel, views, durasi, upload) + pemutar audio** dalam satu pesan; bertahap jika Telegram menolak (animasi → video tanpa suara → video bersuara + audio → video saja).
- Video > `PLAY_VIDEO_MAX_SECS` (15 menit) otomatis memakai thumbnail + MP3.
- Mode klasik (`PLAY_VIDEO=0`): thumbnail + file audio MP3.

### 🎧 Spotify & Mini App

- `spotify <judul>` → daftar bertombol dengan halaman ◀️ ▶️; ketuk nomor untuk memutar (lewat fitur `play`).
- `spotify` → membuka **Mini App** bergaya kartu Spotify.
- Mini App: tombol **+** pada tiap lagu, tab **Playlist** (putar urut/acak, ulang, kosongkan, hapus ✕), pergantian lagu otomatis saat habis (pemutar di dalam Mini App), lagu berikutnya disiapkan lebih dulu, tombol ⏮ ⏭, serta **lirik** dari [lrclib.net](https://lrclib.net).
- Sumber pencarian: Spotify API jika ada kredensial, jika tidak **iTunes**.
- Perlu `SPOTIFY_WEBAPP_URL` (HTTPS publik, mis. lewat Cloudflare Tunnel yang diarahkan ke `http://localhost:8090`).
- Cache video Mini App: `~/.spotify_vcache`, menyimpan `SPOTIFY_VIDEO_KEEP` video terakhir.

### 📥 TikTok

- `tt <link>` (juga `/tt`, `tiktok <link>`, atau kirim link TikTok saja).
- Video **tanpa watermark** (HD bila ada) atau slideshow foto (dikirim per 10 foto) beserta musiknya; `tt mp3 <link>` untuk audio saja.
- Sumber utama **tikwm.com**, cadangan `yt-dlp`. Link pendek `vt.` / `vm.tiktok.com` didukung.

### 📸 Instagram

- `ig <link>` (juga `/ig`, `instagram <link>`, atau kirim link saja): post, reel, IGTV, foto, carousel (semua item, per 10), dengan tabel info dan deskripsi. `ig mp3 <link>` untuk audio saja.
- Sumber utama `yt-dlp`, cadangan halaman embed (post publik).
- **Story, highlight, dan akun privat** butuh cookie login di `~/ig-cookies.txt` (format Netscape). Instagram sering membatasi bot; jika gagal: `pip install -U yt-dlp`.

### 🗜️ Kompres File

Kirim file dengan caption `compres 60mb` (juga `kompres`; satuan `kb`/`mb`/`gb`, tanpa satuan = mb).

| Jenis | Cara |
|---|---|
| Video | Turunkan bitrate & resolusi sesuai target |
| Foto | Kecilkan kualitas & dimensi |
| PDF | Ghostscript |
| Word/Excel/PowerPoint | Kecilkan gambar di dalamnya |
| Audio | Konversi MP3 berbitrate pas |
| Lainnya | Dibungkus `.zip` bila memang mengecil |

NAS hanya menyimpan **hasil kompres**; file asli dibuang. Bila sudah di bawah target, disimpan apa adanya; bila tak tercapai, hasil terkecil disimpan dan bot memberi tahu.

### ⏰ Pengingat & Timer

- Chat biasa: `ingatkan aku 30 menit lagi minum obat`, `ingatkan ujian 13 Januari 2027 jam 9 pagi`.
- Jadwal jauh otomatis dapat pengingat awal **H-7** dan **H-1**.
- Pengingat bisa **diulang tiap menit sampai dibalas** (atau menekan tombol OK); AI ikut menagih dengan komentar santai. Atur kebiasaan dengan `spam ya` / `spam tidak` / `spam tanya`.
- Bila bot sempat mati, pengingat tetap terkirim dengan keterangan telat.

### 📰 Info Terjadwal

- `buatin info nanti jam 6.09 untuk berita hot` atau `setiap hari jam 6.00 carikan 20 berita, poin-poin saja`.
- Pada jam yang dijadwalkan bot **mencari baru di internet** (bukan dari riwayat), lalu mengirim hasil lengkap dengan sumber dan tanggal.
- Untuk pertandingan olahraga: tanggal & jam kick-off (WIB), status SELESAI / BERLANGSUNG / BELUM DIMAINKAN.
- Jika pencarian gagal, bot mengatakan gagal dan **tidak** menjawab dari ingatan AI.

### 📝 Catatan Cepat

`catat …` menyimpan; `catatan` daftar; `catatan <kata>` mencari; `hapus catatan <no>` menghapus. AI dapat menjawab dari catatanmu.

### 🎨 Stiker Teks

`stiker <teks>` → stiker putih berpojok bulat, teks hitam tebal kapital, ukuran huruf otomatis (maks 300 karakter). Dikirim ke chat peminta dan **tidak** disimpan di NAS. Butuh Pillow.

### 🎮 Tic Tac Toe

`ttt` (juga `/ttt`, `tictactoe`, `xo`) membuka Mini App papan 3×3: lawan bot dalam **4 tingkat** (Mudah, Sedang, Sulit, Mustahil) atau **lawan teman** yang terdaftar di bot (undangan lewat pesan bot). Ada **Ulang ronde** dan **Reset skor**. Butuh `SPOTIFY_WEBAPP_URL` terisi.

---

## 👑 Fitur Khusus Pemilik

### Manajemen pengguna

- `id 123456789` tambah, `hapusid 123456789` hapus, `listid` daftar (jumlah tak dibatasi bila `MAX_EXTRA_IDS=0`).
- ID terkunci yang menekan **Minta akses** akan dikabarkan ke pemilik dengan tombol **Setujui / Tolak** (notifikasi sama tidak diulang lebih sering dari sekali per jam). Peminta juga mendapat tombol WhatsApp.

### Blokir ID

- `blok <id>` (juga `blokir`, `ban`) hanya untuk ID **terdaftar**; pemilik tidak bisa diblokir.
- ID terblokir tidak bisa memakai fitur apa pun kecuali `/start` dan Menu Fitur; menerima pesan peringatan (dengan jeda).
- `bukablok <id>` (juga `unblok`, `unban`) mendaftarkan ulang otomatis. `listblok` menampilkan daftar.
- Pengingat, info terjadwal, laporan harian, dan pengumuman tidak dikirim ke ID terblokir.

### Riwayat pengunjung

Setiap ID yang **pertama kali** menekan `/start` dicatat dan pemilik langsung dikabari (nama, ID, username, tanggal & jam WIB, status, urutan pengunjung). Catatan permanen: `~/riwayat-pengunjung-bot.xlsx` (butuh `openpyxl`) dan `.csv`. Perintah `pengunjung` menampilkan total, 10 terbaru, dan mengirim file Excel.

### Laporan harian & peringatan otomatis

- Laporan jam **07:00** (ubah dengan `laporan jam 06:30`): status server, pengingat hari ini, file masuk kemarin.
- Peringatan (dan kabar pulih) untuk: **ESP32** tidak merespons (3 kali gagal beruntun), **Nginx** mati, **Cloudflare tunnel** mati, **SSH** mati, **baterai** ≤ 10% dan tidak dicas (diulang tiap 30 detik sampai dicas atau kirim `berhenti`), **disk** ≥ 90%.

### Update script lewat Telegram

1. Kirim file `.sh` baru dengan caption `update script`.
2. Bot memeriksa **sintaks**, token, ID pemilik, dan keberadaan fitur update; file yang salah **ditolak** dan script lama tidak disentuh.
3. Membuat cadangan (`~/telegram-control-backup`, 5 terakhir), mengganti script, memberi izin eksekusi, restart sendiri.
4. Script baru harus melapor aktif dalam **2 menit**; jika tidak, **versi lama dikembalikan otomatis**.

### Kendali Termux

- `/termux <permintaan biasa>` → AI menyusun **satu** perintah shell, bot menampilkannya, jalan **setelah kamu membalas `ya`** (`batal` untuk membatalkan; hangus 2 menit).
- `/cmd <perintah>` → dijalankan persis seperti ditulis, tetap perlu `ya`.
- Hasil dikirim kembali dengan **token/API key disamarkan**, dijelaskan AI; batas waktu 2 menit.
- Riwayat perintah dicatat di `~/.telegram_termux_log` (200 baris terakhir).
- `TERMUX_SAFETY=1` mengaktifkan daftar larangan (fork bomb, hapus massal, mematikan bot, dll.). Bawaan script ini `0` (**tanpa larangan**) — baca perintah baik-baik sebelum membalas `ya`.

### Foto kamera HP server

`foto` / `foto depan` / `foto belakang` (butuh Termux:API + izin kamera). Foto **tidak disimpan** di HP maupun NAS dan terhapus dari chat setelah 60 detik (`FOTO_HAPUS_DETIK`).

### NAS semua ID

- `nas all id` — ringkasan NAS semua ID terdaftar; `nas all id 03-10-2026` — file tanggal itu di semua ID.
- `nas id <id> <tanggal>` — kirim file milik ID itu; `nas id <id>` — ringkasan.
- `hapus nas id <id> <tanggal>` / `... foto <tanggal> 5 6` / `... semua` — hapus **permanen** setelah konfirmasi `ya`. Orangnya tidak diberi tahu otomatis.

### Dashboard web (PLTS / Maintenance)

`plts` / `maintenance` menjalankan `~/set-mode.sh <mode>`; mode saat ini dibaca dari `~/www/mode.txt`. Kirim file `.html` terlebih dulu untuk mengganti dashboard.

---

## 📏 Batas Ukuran, Durasi, dan Waktu

Nilai di bawah adalah **bawaan script** (`0` = tanpa batas).

| Fitur | Batas ukuran | Batas durasi / waktu |
|---|---|---|
| `ytdl` | `YTDL_MAX_MB=0` | `YTDL_MAX_SECS=0`; unduhan `yt-dlp` tanpa timeout; kirim ke Telegram maks 1800 dtk |
| `play` | `PLAY_MAX_MB=0` | video ≤ 900 dtk (15 menit), lebih panjang → thumbnail + MP3; kirim maks 1800 dtk |
| `yt` / `ytraw` | `YT_MAX_CHARS=0` (transkrip) | pengambilan data `yt-dlp`: 120 / 180 dtk; subtitle 300 dtk |
| Cache video Mini App | `--max-filesize 90M` | unduh maks 420 dtk |
| Pengiriman NAS | `NAS_FILE_MAX_BYTES=0` | `NAS_SEND_TIMEOUT=0` |
| Baca dokumen | `DOC_READ_CHARS=1000000` | OCR PDF s.d. `DOC_OCR_MAX_MB=1024` |
| Halaman web | > 100 MB ditanyakan dulu | tunggu jawaban 300 dtk; macet total 120 dtk |
| Perintah Termux | – | 120 dtk |
| Update script | `UPDATE_MAX_BYTES=3000000` | rollback bila tak aktif 120 dtk |

> **Server Telegram resmi** (bukan lokal): batas kirim bot sekitar 50 MB dan unduh 20 MB. Set `NAS_FILE_MAX_BYTES=50000000`, `YTDL_MAX_MB=49`, `PLAY_MAX_MB=49`.

---

## 🗂️ File yang Dibuat Bot

Semua berada di `$HOME` (home Termux).

| Lokasi | Isi |
|---|---|
| `~/nas_storage/` | NAS pemilik |
| `~/nas_users/<id>/` | NAS tiap pengguna |
| `~/.nas_index` | Indeks pencarian NAS |
| `~/.telegram_extra_ids` | Pengguna tambahan |
| `~/.telegram_blocked` | ID terblokir |
| `~/.telegram_visitors`, `riwayat-pengunjung-bot.xlsx/.csv` | Riwayat pengunjung |
| `~/.telegram_reminders`, `~/.telegram_reminders_active` | Pengingat terjadwal / aktif |
| `~/.telegram_spam_pref` | Preferensi spam pengingat per chat |
| `~/.telegram_schedinfo` | Info terjadwal |
| `~/.telegram_notes` | Catatan |
| `~/.telegram_daily_subs`, `_time`, `_last` | Pengaturan laporan harian |
| `~/.telegram_health_state`, `~/.telegram_monitor_off` | Status & saklar monitor |
| `~/.telegram_offset` | Offset update Telegram |
| `~/.telegram_termux_log` | Audit perintah Termux |
| `~/.gemini_history_<chat_id>.json` | Ingatan AI per chat |
| `~/.web_cache/` | Cache sementara hasil pencarian (dihapus setelah jawaban) |
| `~/.spotify_*` | Token, hasil, antrian, cache video Spotify |
| `~/.spotify_miniapp.py`, `~/spotify-app.log` | Server Mini App (ditulis ulang tiap start) & lognya |
| `~/telegram-control-backup/` | Cadangan script |
| `~/telegram-control.log` | Log |
| `~/yt-cookies.txt`, `~/ig-cookies.txt` | Cookie opsional (**jangan di-commit**) |
| `~/banner.jpg` / `~/banner.mp4` | Banner `/start` |

---

## 🔐 Keamanan

> ⚠️ **Jangan pernah meng-upload script dengan token/API key asli ke GitHub.** Bot yang token-nya bocor bisa diambil alih siapa saja; API key bocor bisa dipakai orang lain sampai kuota habis.

**Sebelum meng-commit:**

1. Ganti nilai berikut dengan placeholder:
   ```bash
   TELEGRAM_TOKEN="ISI_TOKEN_BOT_KAMU"
   OWNER_CHAT_ID="ISI_CHAT_ID_KAMU"
   GEMINI_API_KEY="ISI_API_KEY_GEMINI_KAMU_DI_SINI"
   LOCK_WA_NUMBER="62XXXXXXXXXX"
   SPOTIFY_WEBAPP_URL=""
   ```
2. Jika token/API key **pernah** tertulis di file yang dibagikan atau di-commit: **cabut dan buat ulang** — `/revoke` di @BotFather dan hapus + buat key baru di Google AI Studio. Menghapus commit saja tidak cukup karena riwayat git tetap menyimpannya.
3. Tambahkan ke `.gitignore`: `yt-cookies.txt`, `ig-cookies.txt`, `*.log`, `.env`.

**Praktik aman saat dijalankan:**

- Whitelist ID: hanya ID terdaftar yang dilayani; pesan ID lain diabaikan atau dibalas "terkunci".
- Perintah Termux **selalu** meminta konfirmasi `ya`; output disamarkan dari token/API key.
- `TERMUX_SAFETY=0` berarti **tidak ada** daftar larangan — pertimbangkan `1` bila bot dipakai di lingkungan yang tidak sepenuhnya tepercaya.
- `FOTO_BOLEH_SEMUA=1` memberi semua ID terdaftar akses kamera HP server; biarkan `0`.
- Kode rahasia `nas all id` / `nas id` / `hapus nas id` bisa dipakai ID terdaftar mana pun yang mengetahuinya (hanya pemilik yang melihatnya di menu). Jangan sebarkan.
- Pesan kamera dihapus otomatis; foto tidak disimpan.
- Catatan pengguna dan isi dokumen dikirim ke Google Gemini sebagai konteks — jangan menyimpan rahasia di sana.

---

## 🛠️ Pemecahan Masalah

| Masalah | Solusi |
|---|---|
| `yt-dlp belum terpasang` | `pip install -U yt-dlp` |
| YouTube menolak / dianggap bot | Perbarui `yt-dlp`; simpan cookie di `~/yt-cookies.txt`; tunggu beberapa menit |
| Video dibatasi umur / privat | Butuh cookie YouTube; video privat tidak bisa |
| Instagram gagal | Perbarui `yt-dlp`; story/akun privat butuh `~/ig-cookies.txt` |
| MP3 tidak jadi / audio `m4a` | `pkg install ffmpeg` |
| Kompres PDF gagal | `pkg install ghostscript` |
| Teks PDF tidak terbaca | `pkg install poppler`; PDF terkunci tidak bisa dibaca |
| Stiker gagal | `pkg install python-pillow` |
| File Excel pengunjung tidak ada (hanya CSV) | `pip install openpyxl` |
| Perintah `foto` gagal | `pkg install termux-api` + pasang aplikasi Termux:API + izin kamera |
| Uptime "tidak tersedia" | `pkg install procps` |
| File besar gagal dikirim | Pastikan memakai server Bot API **lokal**; atau set batas ke 49–50 MB untuk server resmi |
| "Fitur AI belum aktif" | Isi `GEMINI_API_KEY` |
| Mini App / `ttt` tidak muncul | Isi `SPOTIFY_WEBAPP_URL` dengan URL HTTPS publik yang menuju port `8090` |
| Menu fitur tampil sebagai teks, bukan tabel | Bot API belum mendukung `sendRichMessage`; script otomatis memakai menu teks |
| Bot berhenti saat Termux ditutup | `termux-wake-lock` + jalankan di `tmux` |
| Folder sementara menumpuk setelah bot mati mendadak | Bersihkan manual isi folder temp Termux (`$TMPDIR`) |
| Update script ditolak | Pastikan file lolos `bash -n`, memuat token & ID pemilik, dan fitur update masih ada |

---

## 🧩 Struktur Script

Script terdiri dari blok fitur bertanda `# >>> FITUR … <<<`:

| Bagian | Isi |
|---|---|
| Konfigurasi awal | Token, ID, batas, jalur file, pengaturan pencarian web, update, Termux |
| **FITUR YT** | `yt`, `ytraw` (transkrip, terjemah, kirim per pesan/file), `play` |
| **FITUR TIKTOK** | `tt` (API tikwm + cadangan `yt-dlp`) |
| **FITUR INSTAGRAM** | `ig` (`yt-dlp` + cadangan embed) |
| **FITUR DOWNLOAD YOUTUBE** | `ytdl`, `ytmp3` (+ tabel info, kirim gabungan) |
| Log & utilitas | `log()`, kirim pesan, pembatas whitelist |
| **FITUR KOMPRES FILE** | Video, foto, PDF, Office, audio, zip |
| Pencarian web | DuckDuckGo, pembacaan halaman, penilaian sumber, verifikasi foto |
| NAS | Simpan, indeks, cari, kirim, hapus, NAS semua ID |
| AI | Gemini, ingatan, penanda `[[...]]`, baca dokumen & OCR |
| Pengingat / catatan / info terjadwal | Penjadwalan dan pengulangan |
| Monitoring | Health check, laporan harian, status server |
| Admin | ID, blokir, pengunjung, update script, Termux, foto |
| Menu & sambutan | `bot_welcome_html`, `bot_help_table_md`, `bot_help_html`, `bot_help_full_html` |
| **FITUR SPOTIFY** | Pencarian, hasil bertombol, server Mini App (Python `http.server`), playlist, lirik |
| **FITUR GAME TIC TAC TOE** | Mini App game |
| Loop utama | Polling `getUpdates`, perutean perintah, pengecekan berkala |

> Menambah fitur baru: tambahkan satu baris di `bot_help_table_md` (menu tabel) dan ubah **kedua** teks bantuan (`bot_help_html` dan `bot_help_full_html`) agar AI ikut mengetahui fitur tersebut.

### Penanda AI (internal)

Gemini menulis penanda ini di akhir jawabannya; script yang menjalankannya dan menyembunyikannya dari pengguna.

| Penanda | Fungsi |
|---|---|
| `[[INGATKAN: WAKTU \| isi \| spam/tanpa-spam]]` | Membuat pengingat (relatif `+30m`, `+2h`, `+3d`, `+2w` atau `DD-MM-YYYY HH:MM`) |
| `[[CARI_FILE: kata \| periode \| kirim]]` | Mencari file di NAS |
| `[[KIRIM_FILE: ...]]` | Mengirim satu file tertentu dari NAS |
| `[[LIHAT_NAS: semua / DD-MM-YYYY]]` | Melihat isi NAS |
| `[[HAPUS_NAS: jenis \| tanggal \| nomor]]` | Meminta penghapusan file NAS (tetap perlu konfirmasi `ya`) |
| `[[CATAT: isi]]` | Menyimpan catatan |
| `CARI_WEB` | Memicu pencarian DuckDuckGo |

---

## 🙌 Kredit

- **Developer:** Moh Hilmi Mulia R. — pelajar TITL (Teknik Instalasi Tenaga Listrik) SMKN 1 Singosari
- **Tim:** MP (Minions Project)
- **Portofolio:** <https://portofolio-by-mp.github.io/Data-percobaan-/>
- **Sertifikat Google Student Developer:** <https://me.developers.google.com/u/hilmistudentdevmalang>

**Layanan & proyek yang dipakai:** [Telegram Bot API](https://core.telegram.org/bots/api) · [Google Gemini API](https://ai.google.dev) · [yt-dlp](https://github.com/yt-dlp/yt-dlp) · [FFmpeg](https://ffmpeg.org) · [DuckDuckGo](https://duckduckgo.com) · [tikwm.com](https://www.tikwm.com) · [lrclib.net](https://lrclib.net) · [iTunes Search API](https://developer.apple.com/library/archive/documentation/AudioVideo/Conceptual/iTuneSearchAPI/) · [Spotify Web API](https://developer.spotify.com/documentation/web-api) · [Termux](https://termux.dev) · [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/)

---

## 📄 Lisensi

Tambahkan file `LICENSE` sesuai pilihanmu (misalnya MIT) sebelum mempublikasikan repo.

> **Disclaimer:** Unduh konten dari YouTube, TikTok, dan Instagram hanya untuk keperluan pribadi dan sesuai ketentuan layanan serta hak cipta di negaramu. Penulis tidak bertanggung jawab atas penyalahgunaan.

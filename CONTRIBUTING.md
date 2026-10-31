# 🤝 Membagikan atau Mem-fork Script

Panduan ini untuk **pemilik repo, kontributor, dan siapa pun yang ingin meng-upload script ini ke GitHub**. Pengguna biasa tidak perlu membacanya; cukup ikuti [README](README.md).

> ⚠️ **Jangan pernah meng-upload script dengan token/API key asli ke GitHub.** Bot yang token-nya bocor bisa diambil alih siapa saja; API key bocor bisa dipakai orang lain sampai kuota habis.

## Sebelum meng-commit

1. Pastikan nilai berikut **kosong** di file yang akan di-upload:
   ```bash
   TELEGRAM_TOKEN=""
   OWNER_CHAT_ID=""
   GEMINI_API_KEY=""
   DEVELOPER_CHAT_ID=""
   LOCK_WA_NUMBER=""
   LOCK_WA_DISPLAY=""
   SPOTIFY_CLIENT_ID=""
   SPOTIFY_CLIENT_SECRET=""
   SPOTIFY_WEBAPP_URL=""
   ```
   Cek cepat sebelum `git add` (tidak boleh ada hasil berisi nilai asli):
   ```bash
   grep -nE '^(TELEGRAM_TOKEN|OWNER_CHAT_ID|GEMINI_API_KEY|DEVELOPER_CHAT_ID|LOCK_WA_NUMBER|SPOTIFY_CLIENT_SECRET)=' telegram-control-local.sh
   ```
2. Jika token/API key **pernah** tertulis di file yang dibagikan atau di-commit: **cabut dan buat ulang** — `/revoke` di @BotFather dan hapus + buat key baru di Google AI Studio. Menghapus commit saja tidak cukup karena riwayat git tetap menyimpannya.
3. Gunakan file `.gitignore` yang disertakan di repo (mengabaikan `yt-cookies.txt`, `ig-cookies.txt`, `*.log`, `.env`, data NAS, riwayat AI, dll.).

## Mem-fork

Teks identitas pembuat ada di `DEVELOPER_PROMPT_BASE` dan `DEVELOPER_CHAT_ID`. Ganti dengan milikmu bila tidak ingin AI memperkenalkan dirinya sebagai buatan orang lain.

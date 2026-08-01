# 🔬 LabKeeper

Sistem peminjaman alat lab sekolah berbasis QR Code untuk Android & iOS.
Stack: Flask + SQLite (zero-cost, jalan di laptop sekolah).

---

## ✨ Fitur

### Untuk Siswa
- 📱 **Scan QR** di belakang alat → langsung lihat status & foto alat (pakai kamera HP)
- 🔐 Login pakai **NIS** untuk pinjam/kembalikan
- ⏱️ Lihat **countdown real-time** berapa lama lagi harus dikembalikan
- 📜 Riwayat peminjaman pribadi

### Untuk Admin (Laboran)
- 📊 Dashboard dengan **live countdown** semua peminjaman aktif
- 📦 CRUD alat lengkap dengan auto-generate QR code
- 👥 Kelola data siswa + reset password
- 🚨 Force-return alat telat + catat kondisi (Baik/Rusak Ringan/Rusak Berat)
- 🏷️ Cetak halaman QR label (semua alat) untuk print & tempel
- ⚙️ Pengaturan: nama sekolah, base URL, durasi pinjam

---

## 🚀 Quick Start (lokal / demo)

```bash
# 1. Setup
cd labkeeper
python -m venv venv
source venv/Scripts/activate        # Windows (Git Bash)
# source venv/bin/activate          # macOS / Linux

pip install -r requirements.txt

# 2. Seed data (admin + 20 alat + 5 siswa + 1 sample loan)
python seed.py

# 3. Jalankan
python app.py
```

Buka di browser:
- **Siswa**: http://localhost:5000
- **Admin**: http://localhost:5000/admin/login
  - username: `admin`
  - password: `admin123`

Siswa contoh:
- NIS: `1001` s/d `1005`
- Password: `siswa123`

---

## 📱 Cara Pakai di HP Siswa (WiFi Sekolah)

1. Jalankan server di laptop laboran: `python app.py`
   - Catat IP laptop (misal `192.168.1.10`) — server jalan di `0.0.0.0:5000`
2. Siswa konek WiFi sekolah yang sama
3. Buka di HP: `http://192.168.1.10:5000`
4. **Bookmark** atau "Add to Home Screen" supaya iconnya muncul di home screen seperti aplikasi native
5. Scan QR yang ditempel di belakang alat → otomatis login (kalau sudah) → pinjam

> 💡 Untuk **HTTPS** (diperlukan agar kamera bisa jalan di iOS Safari & Chrome Android non-localhost), pakai:
> - **Cloudflare Tunnel** (gratis): `cloudflared tunnel --url http://localhost:5000`
> - **ngrok**: `ngrok http 5000`

---

## 🗂️ Struktur File

```
labkeeper/
├── app.py                    # Main Flask app (routes, factory pattern)
├── models.py                 # SQLAlchemy models (Student, Admin, Tool, Borrowing, Config)
├── auth.py                   # Decorators: @student_required, @admin_required
├── qr_utils.py               # QR generation (qrcode + PIL)
├── seed.py                   # Database seeding script
├── requirements.txt
├── README.md
├── PROJECT_TREE.md
│
├── instance/labkeeper.db     # SQLite database (auto-created by Flask-SQLAlchemy)
│
├── static/
│   ├── css/app.css           # Mobile-first styles
│   ├── js/countdown.js       # Live countdown JS (vanilla)
│   └── qr_codes/*.png        # Auto-generated QR per tool
│
└── templates/
    ├── base.html             # Public base layout
    ├── admin_base.html       # Admin base layout (sidebar)
    ├── index.html            # Homepage (list semua alat)
    ├── scan.html             # QR scanner page (jsQR)
    ├── tool_detail.html      # Halaman alat (lihat detail + pinjam/kembalikan)
    ├── login.html            # Student login
    ├── pinjam.html           # Konfirmasi pinjam
    ├── history.html          # Riwayat siswa
    ├── admin/
    │   ├── admin_login.html
    │   ├── dashboard.html    # ⭐ Live countdown dashboard
    │   ├── tools_list.html
    │   ├── tool_form.html
    │   ├── borrowings_list.html
    │   ├── students_list.html
    │   ├── student_form.html
    │   ├── qr_labels.html    # Print semua QR
    │   └── settings.html
    └── (admin_*.html lain di root juga OK, strukturnya fleksibel)
```

---

## 🔌 API Endpoints

| Endpoint | Method | Auth | Fungsi |
|---|---|---|---|
| `/` | GET | - | Homepage, list alat |
| `/tool/<code>` | GET | - | Detail alat publik |
| `/scan` | GET | - | Halaman QR scanner |
| `/student/login` | GET/POST | - | Login siswa |
| `/logout` | GET | - | Logout |
| `/pinjam/<code>` | GET/POST | Student | Pinjam alat |
| `/kembalikan/<code>` | POST | Student | Kembalikan alat |
| `/riwayat` | GET | Student | Riwayat pribadi |
| `/admin/login` | GET/POST | - | Login admin |
| `/admin/dashboard` | GET | Admin | Dashboard live |
| `/admin/tools` `/new` `<id>/edit` `<id>/regenerate-qr` `<id>/delete` | GET/POST | Admin | CRUD alat |
| `/admin/borrowings` `<bid>/force-return` | GET/POST | Admin | Kelola peminjaman |
| `/admin/students` `/new` `<sid>/reset-password` | GET/POST | Admin | Kelola siswa |
| `/admin/qr-labels` | GET | Admin | Print semua QR |
| `/admin/settings` | GET/POST | Admin | Pengaturan |
| `/api/active-borrowings` | GET | Admin | JSON untuk AJAX |

---

## ⚙️ Konfigurasi

Edit file `.env` (opsional):

```bash
SECRET_KEY=ganti-dengan-string-random-32-char
```

Atau langsung edit `app.py` bagian `app.config["SECRET_KEY"]`.

Untuk **ganti URL QR** (misal sudah deploy ke internet), buka `/admin/settings` setelah login sebagai admin.

---

## 🔐 Catatan Keamanan (untuk produksi)

Sistem ini di-rancang untuk **lingkungan intranet sekolah** (WiFi lokal). Kalau mau expose ke internet:

- [ ] **Ganti `SECRET_KEY`** dengan string random
- [ ] **HTTPS wajib** — pakai Cloudflare Tunnel / Let's Encrypt
- [ ] Ganti `admin123` / `siswa123` password default
- [ ] Tambah rate limiting (Flask-Limiter)
- [ ] Ganti SQLite → PostgreSQL untuk concurrency lebih tinggi

---

## 📜 Lisensi

MIT — bebas dipakai, dimodifikasi, disebarluaskan untuk kebutuhan edukasi Indonesia.
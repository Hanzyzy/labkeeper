# 🔬 LabKeeper — Sistem Manajemen Peminjaman Alat Lab Sekolah

**LabKeeper** adalah platform web manajemen peminjaman alat laboratorium sekolah berbasis QR Code yang mendukung arsitektur **Multi-Sekolah (Multi-Tenant)**. Aplikasi ini dirancang mobile-first, responsif, modern, dan sangat mudah digunakan oleh siswa maupun pengelola lab (laboran/admin).

---

## ✨ Fitur-Fitur Utama

### 🏫 1. Multi-Sekolah (Multi-Tenant) Terisolasi
* **Isolasi Data Per Sekolah**: Setiap sekolah memiliki data alat, siswa, admin, serta riwayat peminjaman yang terisolasi 100%.
* **Aturan Durasi Peminjaman Independen (`School.loan_duration_hours`)**: Admin Sekolah A dapat menetapkan durasi peminjaman (misal 3 jam) tanpa mempengaruhi aturan di Sekolah B (misal 24 jam).
* **Manajemen Multi-Sekolah Mudah**: Dilengkapi script interaktif `add_school.py` untuk mendaftarkan sekolah dan akun admin baru secara instan.

### 📱 2. Fitur Siswa
* **Scan QR Code Alat**: Peminjaman alat secara otomatis melalui pemindaian QR Code dari kamera HP (Android & iOS).
* **Live Countdown Timer**: Penghitung waktu mundur peminjaman secara real-time.
* **Perpanjangan Waktu Peminjaman**: Permohonan perpanjangan durasi pinjam langsung dari dashboard siswa (maksimal 2x perpanjangan).
* **Profil & Keamanan**: Pengubahan kata sandi siswa dengan invalidasi sesi multi-perangkat (password versioning).

### 🛠️ 3. Fitur Admin (Laboran)
* **Dashboard Live Monitoring**: Monitoring peminjaman aktif dengan indikator warna status (*Aktif / Kembali / Overdue*).
* **CRUD Alat Lab & Auto-Generate QR Code**: Pembuatan alat baru dengan QR Code PNG yang digenerate otomatis.
* **Cetak Label QR Code**: Fitur pencetakan massal atau terpilih untuk stiker label QR alat lab.
* **Import & Export Excel (`.xlsx`)**: Import massal data siswa dan alat lab via file Excel beserta preview validasi data.
* **Pengaturan Sistem & Keamanan**: Pengubahan kata sandi admin dengan enkripsi aman, serta pemeliharaan data.

### 🌐 4. Integrated Web Database Management (`sqlite-web`)
* **Web Database GUI 24/7**: Terintegrasi dengan `sqlite-web` service di port `8080` untuk pengelolaan SQLite via browser.
* **Proteksi Password**: Dilengkapi sistem autentikasi password terenkripsi untuk keamanan akses web database.

---

## 🛠️ Arsitektur & Teknologi (Tech Stack)

| Komponen | Teknologi / Library |
|---|---|
| **Core Framework** | Python 3.11 / Flask 3.0 |
| **Database & ORM** | SQLite 3 / Flask-SQLAlchemy 3.1 |
| **Authentikasi** | Werkzeug Security (Scrypt & PBKDF2 Password Hashing) |
| **QR Code Engine** | `qrcode[pil]` (Pillow Image Generator) |
| **Excel Engine** | `openpyxl` (Import & Styled Export) |
| **Zona Waktu** | `Asia/Jakarta` (Waktu Indonesia Barat / WIB - UTC+7) |
| **Frontend Layout** | Jinja2 Templates, HTML5 Semantic, Custom Vanilla CSS (Bento Grid) |
| **Production Server** | Gunicorn (3 Workers) + Nginx Reverse Proxy + Certbot SSL |

---

## 🗂️ Struktur Direktori Proyek

```text
labkeeper/
├── app.py                  # Main Flask Application (Routes & Logic)
├── models.py               # SQLAlchemy ORM Models (School, Admin, Student, Tool, Borrowing, Config)
├── auth.py                 # Authentication Helpers & Session Decorators
├── datetime_utils.py       # Timezone WIB (Asia/Jakarta) Helpers & Utilities
├── qr_utils.py             # QR Code Generator using Pillow
├── reset_db.py             # Script Reset & Seeding Initial Data
├── add_school.py           # Script Interaktif Tambah Sekolah & Admin Baru
├── fix_db.py               # Script Perbaikan Format Tanggal Database
├── deploy_vps.sh           # Script Deployment VPS Otomatis
├── requirements.txt        # Python Dependencies
├── README.md               # Dokumentasi Resmi Proyek
│
├── instance/
│   └── labkeeper.db        # File Database SQLite
│
├── static/
│   ├── css/new_style.css   # Custom CSS Styling & Responsive Design
│   ├── js/countdown.js     # Live Countdown Timer Vanilla JS
│   ├── images/             # Asset Gambar Logo & Hero Banner
│   ├── qr_codes/           # File Gambar PNG QR Code Alat Lab
│   └── uploads/            # File Avatar Siswa & Foto Alat
│
└── templates/
    ├── base.html           # Public Base Layout Template
    ├── admin_base.html     # Admin Sidebar Base Template
    ├── index.html          # Halaman Beranda & Katalog Sekolah
    ├── scan.html           # Halaman Scanner QR Code
    ├── tool_detail.html    # Detail Alat Lab
    ├── login.html          # Login Siswa
    ├── pinjam.html         # Form Konfirmasi Pinjam
    ├── history.html        # Riwayat Peminjaman Siswa
    └── admin/
        ├── admin_login.html# Login Admin Sekolah
        ├── dashboard.html  # Live Dashboard Monitoring
        ├── tools.html      # Kelola Alat Lab
        ├── tool_form.html  # Form Tambah/Edit Alat
        ├── students.html   # Kelola Data Siswa
        ├── borrowings.html # Kelola & Export Peminjaman
        ├── qr_labels.html  # Cetak Label QR Code
        └── settings.html  # Pengaturan Sistem & Keamanan
```

---

## 🚀 Panduan Penggunaan Script Pembantu

### 1. Menambah Sekolah & Admin Baru (CLI Interaktif)
```bash
cd /var/www/labkeeper
source venv/bin/activate
python3 add_school.py
```

### 2. Reset & Seed Data Awal
```bash
python3 reset_db.py
```

### 3. Memperbaiki Format Tanggal SQLite (jika di-input manual)
```bash
python3 fix_db.py
```

---

## 🌐 Layanan Web GUI Database Management (`sqlite-web`)

Untuk mengakses GUI database berbasis browser (mirip phpMyAdmin):

* **URL**: `http://IP_VPS_ANDA:8080` (Contoh: `http://43.129.49.162:8080`)
* **Password**: `262010`

### Menjalankan Service Nonstop (Systemd):
```bash
echo '[Unit]
Description=SQLite Web GUI Manager for LabKeeper
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/var/www/labkeeper
Environment="SQLITE_WEB_PASSWORD=262010"
ExecStart=/var/www/labkeeper/venv/bin/python3 -m sqlite_web /var/www/labkeeper/instance/labkeeper.db --port 8080 --host 0.0.0.0 --password
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target' | sudo tee /etc/systemd/system/sqlite-web.service > /dev/null

sudo systemctl daemon-reload
sudo systemctl restart sqlite-web
```

---

## ⚡ Deployment & Update Cepat di VPS

Untuk memperbarui aplikasi ke versi terbaru di server VPS:

```bash
cd /var/www/labkeeper
git pull && sudo systemctl restart labkeeper
```

---

## 📜 Lisensi

Dokumen dan kode sumber **LabKeeper** dilindungi di bawah lisensi MIT — bebas digunakan, dikembangkan, dan disebarluaskan untuk kebutuhan pendidikan di Indonesia.
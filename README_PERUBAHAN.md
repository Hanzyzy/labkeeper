# 📑 Laporan Perubahan & Dokumentasi Sistem LabKeeper

Dokumen ini berisi rangkuman lengkap mengenai perubahan kode, fitur baru, perbaikan bug, zona waktu, serta pengamanan database web GUI pada sistem **LabKeeper**.

---

## 1. 🏫 Multi-Tenant & Aturan Terisolasi Per Sekolah

### Perubahan & Fitur:
* **Durasi Peminjaman Terisolasi (`School.loan_duration_hours`)**:
  * Setiap sekolah kini memiliki batas waktu peminjaman independen yang disimpan di kolom `loan_duration_hours` pada tabel `schools`.
  * Mengubah durasi peminjaman di **Sekolah A** (misal 3 jam) sama sekali **tidak mempengaruhi Sekolah B** (misal 24 jam).
* **Script Otomatis Tambah Sekolah (`add_school.py`)**:
  * Menambahkan script interaktif [`add_school.py`](file:///C:/Users/Lenovo/labkeeper/add_school.py) untuk mendaftarkan sekolah baru dan akun admin sekolah baru secara langsung.

### Penggunaan CLI VPS:
```bash
cd /var/www/labkeeper
source venv/bin/activate
python3 add_school.py
```

---

## 2. 🕒 Penyesuaian Zona Waktu (WIB - Asia/Jakarta, UTC+7)

### Perubahan & Fitur:
* Seluruh pencatatan waktu (`created_at`, `borrow_date`, `deadline`, `return_date`) disesuaikan secara presisi ke zona waktu **Asia/Jakarta (WIB, UTC+7)** pada file [`app.py`](file:///C:/Users/Lenovo/labkeeper/app.py), [`models.py`](file:///C:/Users/Lenovo/labkeeper/models.py), dan [`datetime_utils.py`](file:///C:/Users/Lenovo/labkeeper/datetime_utils.py).
* Menambahkan script otomatis [`fix_db.py`](file:///C:/Users/Lenovo/labkeeper/fix_db.py) untuk mengonversi string tanggal non-ISO (seperti `DD/MM/YYYY`) menjadi format standar ISO (`YYYY-MM-DD HH:MM:SS`) agar tidak memicu `ValueError` pada SQLAlchemy.

---

## 3. 🛡️ Keamanan Password & Toleransi Login

### Perubahan & Fitur:
* **Auto-Upgrade Password Hash**:
  * Pada file [`models.py`](file:///C:/Users/Lenovo/labkeeper/models.py), metode `check_password` untuk model `Admin` dan `Student` telah diperbarui.
  * Jika password di database berupa teks biasa (akibat di-insert manual via web database), sistem akan secara aman mencocokkan password tersebut dan **secara otomatis meng-upgrade-nya menjadi hash enkripsi Werkzeug** saat pengguna berhasil login.
  * Mencegah terjadinya `500 Internal Server Error` saat login.

---

## 4. 🖨️ Perbaikan Bug Cetak Label QR Code

### Perubahan & Fitur:
* **Fix SyntaxError `querySelector`**:
  * Pada file [`templates/admin/qr_labels.html`](file:///C:/Users/Lenovo/labkeeper/templates/admin/qr_labels.html), elemen ID diubah menggunakan `tool.id` (integer) dan pemilihan teks menggunakan selector `.qr-select-text`.
  * Kode alat yang mengandung spasi (seperti `CTH 09`) tidak lagi menyebabkan `Uncaught SyntaxError`.

---

## 5. 🎨 Proteksi Tampilan Logo (Anti-Distorsi)

### Perubahan & Fitur:
* Menambahkan aturan CSS `object-fit: contain !important; width: auto !important; flex-shrink: 0 !important;` pada file [`static/css/new_style.css`](file:///C:/Users/Lenovo/labkeeper/static/css/new_style.css).
* Logo aplikasi dijamin proporsional pada semua ukuran layar HP (DPI kecil maupun besar).

---

## 6. 🌐 Service Web Database Management (`sqlite-web`)

### Konfigurasi Service Nonstop (`sqlite-web.service`):
Web GUI database berjalan 24/7 di latar belakang VPS pada port `8080` dan dilindungi dengan password **`262010`**.

### Perintah Setup Service VPS:
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

### Akses Web Database GUI:
* **URL**: [http://43.129.49.162:8080](http://43.129.49.162:8080)
* **Password**: `262010`

---

## 🚀 Perintah Deployment / Update Cepat VPS

Tinggal jalankan perintah berikut di terminal VPS untuk menerapkan seluruh update terbaru:

```bash
cd /var/www/labkeeper
git pull && sudo systemctl restart labkeeper
```

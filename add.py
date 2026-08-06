#!/usr/bin/env python3
"""LabKeeper — Script Interaktif Tambah Sekolah & Admin Baru
Dapat dijalankan langsung dari direktori manapun di VPS tanpa mengaktifkan venv.
Penggunaan: python3 /var/www/labkeeper/add.py  ATAU  perintah 'add'
"""
import os
import sys
import subprocess
from datetime import datetime, timezone, timedelta

# Auto-switch working directory to project root
_this_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(_this_dir)

# Auto-include venv site-packages across operating systems and python versions
for _p in [
    os.path.join(_this_dir, "venv", "Lib", "site-packages"),
    os.path.join(_this_dir, "venv", "lib", f"python3.{sys.version_info.minor}", "site-packages"),
    "/var/www/labkeeper/venv/lib/python3.12/site-packages",
    "/var/www/labkeeper/venv/lib/python3.11/site-packages",
    "/var/www/labkeeper/venv/lib/python3.10/site-packages",
]:
    if os.path.exists(_p) and _p not in sys.path:
        sys.path.insert(0, _p)

from app import create_app
from models import db, School, Admin, wib_now
from fix_db import fix_db


def main():
    print("==========================================")
    print("  🏫 TAMBAH SEKOLAH & ADMIN BARU (LABKEEPER)")
    print("==========================================")

    # 1. Tanya Jawab Input Data
    name = input("📌 Nama Sekolah (misal: SMKN 2 Bandung): ").strip()
    code = input("📌 Kode Sekolah (misal: SMKN2-BDG): ").strip().upper()
    address = input("📌 Alamat Sekolah (opsional): ").strip()
    username = input("📌 Username Admin Baru (misal: admin_smkn2): ").strip()
    password = input("📌 Password Admin Baru (misal: admin123): ").strip()
    full_name = input("📌 Nama Lengkap Admin (opsional): ").strip() or f"Admin {name}"

    if not name or not code or not username or not password:
        print("\n❌ [ERROR] Nama sekolah, kode sekolah, username, dan password Wajib diisi!")
        return

    app = create_app()
    with app.app_context():
        # Clean any old invalid dates first
        try:
            fix_db()
        except Exception:
            pass

        # 2. Cek & Buat Sekolah
        sch = School.query.filter_by(code=code).first()
        if not sch:
            sch = School(
                code=code,
                name=name,
                address=address,
                loan_duration_hours=2,
                is_active=True,
                created_at=wib_now()
            )
            db.session.add(sch)
            db.session.commit()
            print(f"✅ [OK] Sekolah '{name}' ({code}) berhasil dibuat!")
        else:
            print(f"ℹ️ [INFO] Sekolah dengan kode '{code}' sudah terdaftar.")

        # 3. Cek & Buat Admin dengan Hashing Password
        adm = Admin.query.filter_by(username=username).first()
        if not adm:
            adm = Admin(
                school_id=sch.id,
                username=username,
                full_name=full_name,
                created_at=wib_now()
            )
            # Encrypt password using Werkzeug hashing
            adm.set_password(password)
            db.session.add(adm)
            db.session.commit()
            print(f"✅ [OK] Admin '{username}' berhasil dibuat & di-encrypt!")
        else:
            print(f"⚠️ [WARNING] Username admin '{username}' sudah ada.")

        # Clean dates again to ensure DB purity
        try:
            fix_db()
        except Exception:
            pass

        print("\n==========================================")
        print("🎉 SUKSES! Sekolah & Admin Siap Digunakan")
        print(f"   Nama Sekolah : {name}")
        print(f"   Kode Sekolah : {code}")
        print(f"   Username     : {username}")
        print(f"   Password     : {password} (TER-ENKRIPSI)")
        print("==========================================")

    # 4. Auto-restart systemd service jika berjalan di VPS Linux
    try:
        res = subprocess.run(["sudo", "systemctl", "restart", "labkeeper"], capture_output=True, text=True)
        if res.returncode == 0:
            print("🔄 [OK] Service LabKeeper berhasil di-restart otomatis!")
    except Exception:
        pass


if __name__ == "__main__":
    main()

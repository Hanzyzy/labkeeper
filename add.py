#!/usr/bin/env python3
"""LabKeeper — Script Interaktif Tambah Sekolah & Admin Baru
Penggunaan: add
"""
import os
import sys
import subprocess

_this_dir = "/var/www/labkeeper"
if os.path.exists(_this_dir):
    os.chdir(_this_dir)
    if _this_dir not in sys.path:
        sys.path.insert(0, _this_dir)
else:
    _this_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(_this_dir)

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
    print("------------------------------------------")
    print(" Tambah Sekolah & Admin Baru - LabKeeper")
    print("------------------------------------------")

    name = input("Nama Sekolah (misal: SMKN 2 Bandung): ").strip()
    code = input("Kode Sekolah (misal: SMKN2-BDG): ").strip().upper()
    address = input("Alamat Sekolah (opsional): ").strip()
    username = input("Username Admin Baru (misal: admin_smkn2): ").strip()
    password = input("Password Admin Baru (misal: admin123): ").strip()
    full_name = input("Nama Lengkap Admin (opsional): ").strip() or f"Admin {name}"

    if not name or not code or not username or not password:
        print("\n[Error] Nama sekolah, kode sekolah, username, dan password wajib diisi.")
        return

    app = create_app()
    with app.app_context():
        try:
            fix_db()
        except Exception:
            pass

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
            print(f"[OK] Sekolah '{name}' ({code}) berhasil dibuat.")
        else:
            print(f"[Info] Sekolah dengan kode '{code}' sudah terdaftar.")

        adm = Admin.query.filter_by(username=username).first()
        if not adm:
            adm = Admin(
                school_id=sch.id,
                username=username,
                full_name=full_name,
                created_at=wib_now()
            )
            adm.set_password(password)
            db.session.add(adm)
            db.session.commit()
            print(f"[OK] Admin '{username}' berhasil dibuat.")
        else:
            print(f"[Warning] Username admin '{username}' sudah terdaftar.")

        try:
            fix_db()
        except Exception:
            pass

        print("------------------------------------------")
        print("Selesai. Sekolah & Admin berhasil ditambahkan.")
        print(f"  Sekolah  : {name} ({code})")
        print(f"  Username : {username}")
        print(f"  Password : {password}")
        print("------------------------------------------")

    try:
        res = subprocess.run(["sudo", "systemctl", "restart", "labkeeper"], capture_output=True, text=True)
        if res.returncode == 0:
            print("[OK] Service LabKeeper berhasil di-restart.")
    except Exception:
        pass


if __name__ == "__main__":
    main()

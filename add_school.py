import os
import sys
import argparse

# Ensure venv site-packages is included for cross-platform support
_this_dir = os.path.dirname(os.path.abspath(__file__))
for _p in [
    os.path.join(_this_dir, "venv", "Lib", "site-packages"),
    os.path.join(_this_dir, "venv", "lib", f"python3.{sys.version_info.minor}", "site-packages"),
]:
    if os.path.exists(_p) and _p not in sys.path:
        sys.path.insert(0, _p)

from app import create_app
from models import db, School, Admin


def add_new_school(name=None, code=None, address="", username=None, password=None, full_name=None):
    app = create_app()
    with app.app_context():
        print("==========================================")
        print("  TAMBAH SEKOLAH & ADMIN BARU — LABKEEPER ")
        print("==========================================")
        
        if not name:
            name = input("Nama Sekolah (misal: SMKN 2 Bandung): ").strip()
        if not code:
            code = input("Kode Sekolah (misal: SMKN2-BDG): ").strip().upper()
        if address is None:
            address = input("Alamat Sekolah (opsional): ").strip()
        
        if not username:
            username = input("Username Admin Baru (misal: admin_smkn2): ").strip()
        if not password:
            password = input("Password Admin (misal: admin123): ").strip()
        if not full_name:
            if name and not sys.stdin.isatty():
                full_name = f"Admin {name}"
            else:
                full_name = input("Nama Lengkap Admin (opsional): ").strip() or f"Admin {name}"
        
        if not name or not code or not username or not password:
            print("[ERROR] Nama sekolah, kode sekolah, username, dan password wajib diisi!")
            return False
            
        try:
            # Check existing school
            sch = School.query.filter_by(code=code).first()
            if not sch:
                sch = School(code=code, name=name, address=address, loan_duration_hours=2, is_active=True)
                db.session.add(sch)
                db.session.commit()
                print(f"[OK] Sekolah '{name}' berhasil dibuat! (ID: {sch.id})")
            else:
                print(f"[INFO] Sekolah dengan kode '{code}' sudah ada (ID: {sch.id}).")
                
            # Check existing admin
            adm = Admin.query.filter_by(username=username).first()
            if not adm:
                adm = Admin(school_id=sch.id, username=username, full_name=full_name)
                adm.set_password(password)
                db.session.add(adm)
                db.session.commit()
                print(f"[OK] Admin '{username}' berhasil dibuat untuk {name}!")
            else:
                print(f"[WARNING] Username admin '{username}' sudah digunakan.")
        except Exception as e:
            db.session.rollback()
            print(f"[ERROR] Gagal menyimpan ke database: {e}")
            return False
            
        print("==========================================")
        print("[DONE] Selesai! Login di Halaman Admin")
        print(f"   Pilih Sekolah : {name}")
        print(f"   Username      : {username}")
        print(f"   Password      : {password}")
        print("==========================================")
        return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Tambah Sekolah & Admin Baru untuk LabKeeper")
    parser.add_argument("--name", help="Nama Sekolah")
    parser.add_argument("--code", help="Kode Sekolah")
    parser.add_argument("--address", default="", help="Alamat Sekolah")
    parser.add_argument("--username", help="Username Admin")
    parser.add_argument("--password", help="Password Admin")
    parser.add_argument("--full-name", help="Nama Lengkap Admin")
    args = parser.parse_args()

    add_new_school(
        name=args.name,
        code=args.code,
        address=args.address,
        username=args.username,
        password=args.password,
        full_name=args.full_name,
    )

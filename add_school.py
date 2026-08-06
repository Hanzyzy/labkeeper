import sys
from app import create_app
from models import db, School, Admin

def add_new_school():
    app = create_app()
    with app.app_context():
        print("==========================================")
        print("  TAMBAH SEKOLAH & ADMIN BARU — LABKEEPER ")
        print("==========================================")
        
        name = input("Nama Sekolah (misal: SMKN 2 Bandung): ").strip()
        code = input("Kode Sekolah (misal: SMKN2-BDG): ").strip().upper()
        address = input("Alamat Sekolah (opsional): ").strip()
        
        username = input("Username Admin Baru (misal: admin_smkn2): ").strip()
        password = input("Password Admin (misal: admin123): ").strip()
        full_name = input("Nama Lengkap Admin (opsional): ").strip() or f"Admin {name}"
        
        if not name or not code or not username or not password:
            print("❌ ERROR: Nama sekolah, kode sekolah, username, dan password wajib diisi!")
            return
            
        # Check existing school
        sch = School.query.filter_by(code=code).first()
        if not sch:
            sch = School(code=code, name=name, address=address)
            db.session.add(sch)
            db.session.commit()
            print(f"✅ Sekolah '{name}' berhasil dibuat! (ID: {sch.id})")
        else:
            print(f"ℹ️ Sekolah dengan kode '{code}' sudah ada.")
            
        # Check existing admin
        adm = Admin.query.filter_by(username=username).first()
        if not adm:
            adm = Admin(school_id=sch.id, username=username, full_name=full_name)
            adm.set_password(password)
            db.session.add(adm)
            db.session.commit()
            print(f"✅ Admin '{username}' berhasil dibuat untuk {name}!")
        else:
            print(f"⚠️ Username admin '{username}' sudah digunakan.")
            
        print("==========================================")
        print(f"🎉 Selesai! Login di https://labkeeper.my.id/admin/login")
        print(f"   Pilih Sekolah : {name}")
        print(f"   Username      : {username}")
        print(f"   Password      : {password}")
        print("==========================================")

if __name__ == "__main__":
    add_new_school()

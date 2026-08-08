from app import create_app
from models import db, School, Admin, Student, Config

def reset_and_seed():
    app = create_app()
    with app.app_context():
        db.drop_all()
        db.create_all()
        
        # 1. Tambah Sekolah Default
        s1 = School(id=1, code="TELKOM-BDG", name="SMK Telkom Bandung", address="Jl. Terusan Buah Batu No. 33")
        s2 = School(id=2, code="SMKN1-JKT", name="SMK Negeri 1 Jakarta", address="Jl. Budi Utomo No. 7")
        s3 = School(id=3, code="SMAN3-SBY", name="SMA Negeri 3 Surabaya", address="Jl. Memet Sastrawidjaja")
        db.session.add_all([s1, s2, s3])
        
        # 2. Config
        cfg = Config(id=1, loan_duration_hours=2, school_name="SMK Telkom Bandung", base_url="https://labkeeper.my.id")
        db.session.add(cfg)
        
        # 3. Akun Admin
        a = Admin(school_id=1, username="admin", full_name="Administrator Lab")
        a.set_password("admin123")
        db.session.add(a)
        
        # 4. Akun Siswa
        siswa_list = [
            ("1001", "Budi Santoso", "XII RPL 1"),
            ("1002", "Siti Nurhaliza", "XII RPL 1"),
            ("1003", "Ahmad Dahlan", "XII TKJ 2"),
            ("1004", "Dewi Sartika", "XI RPL 2"),
            ("1005", "Eko Prasetyo", "X TJA 1"),
        ]
        for nis, name, cls in siswa_list:
            st = Student(school_id=1, nis=nis, name=name, class_name=cls)
            st.set_password("siswa123")
            db.session.add(st)
            
        db.session.commit()
        print("==========================================")
        print("[SUCCESS] DATABASE BERHASIL DI-RESET & DI-SEED!")
        print("Admin: admin / admin123 (SMK Telkom Bandung)")
        print("Siswa: 1001-1005 / siswa123 (SMK Telkom Bandung)")
        print("==========================================")

if __name__ == "__main__":
    reset_and_seed()

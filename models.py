"""LabKeeper — Database Models (SQLAlchemy / SQLite)
Supports Multi-School (Multi-Tenant) Architecture.
"""
from datetime import datetime, timedelta, timezone
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

from sqlalchemy.types import TypeDecorator, DateTime

db = SQLAlchemy()

WIB = timezone(timedelta(hours=7))


def wib_now() -> datetime:
    """Returns naive datetime in Asia/Jakarta timezone (WIB, UTC+7)."""
    return datetime.now(WIB).replace(tzinfo=None)


class SafeDateTime(TypeDecorator):
    """Custom DateTime TypeDecorator that safely parses any datetime format
    (including non-standard ISO strings like '06/08/2026') without raising ValueError.
    """
    impl = DateTime
    cache_ok = True

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            val_str = value.strip()
            if not val_str:
                return None
            try:
                return datetime.fromisoformat(val_str)
            except Exception:
                pass
            if "/" in val_str:
                try:
                    time_part = "00:00:00"
                    date_part = val_str
                    if " " in val_str:
                        date_part, time_part = val_str.split(" ", 1)
                    parts = date_part.split("/")
                    if len(parts) == 3:
                        dd, mm, yyyy = int(parts[0]), int(parts[1]), int(parts[2])
                        h, m, s = 0, 0, 0
                        if ":" in time_part:
                            t_parts = time_part.split(":")
                            h = int(t_parts[0])
                            m = int(t_parts[1]) if len(t_parts) > 1 else 0
                            s = int(t_parts[2]) if len(t_parts) > 2 else 0
                        return datetime(yyyy, mm, dd, h, m, s)
                except Exception:
                    pass
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y"):
                try:
                    return datetime.strptime(val_str, fmt)
                except Exception:
                    pass
            return wib_now()
        return value

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            val_str = value.strip()
            if not val_str:
                return None
            try:
                return datetime.fromisoformat(val_str)
            except Exception:
                pass
            if "/" in val_str:
                try:
                    time_part = "00:00:00"
                    date_part = val_str
                    if " " in val_str:
                        date_part, time_part = val_str.split(" ", 1)
                    parts = date_part.split("/")
                    if len(parts) == 3:
                        dd, mm, yyyy = int(parts[0]), int(parts[1]), int(parts[2])
                        h, m, s = 0, 0, 0
                        if ":" in time_part:
                            t_parts = time_part.split(":")
                            h = int(t_parts[0])
                            m = int(t_parts[1]) if len(t_parts) > 1 else 0
                            s = int(t_parts[2]) if len(t_parts) > 2 else 0
                        return datetime(yyyy, mm, dd, h, m, s)
                except Exception:
                    pass
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y"):
                try:
                    return datetime.strptime(val_str, fmt)
                except Exception:
                    pass
            return wib_now()
        return value


class School(db.Model):
    __tablename__ = "schools"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(30), unique=True, nullable=False, index=True)
    name = db.Column(db.String(150), nullable=False)
    address = db.Column(db.String(255))
    loan_duration_hours = db.Column(db.Integer, default=2, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(SafeDateTime, default=wib_now)

    students = db.relationship("Student", backref="school", lazy=True)
    tools = db.relationship("Tool", backref="school", lazy=True)
    admins = db.relationship("Admin", backref="school", lazy=True)
    borrowings = db.relationship("Borrowing", backref="school", lazy=True)


class Admin(db.Model):
    __tablename__ = "admins"
    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.Integer, db.ForeignKey("schools.id"), nullable=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    full_name = db.Column(db.String(100))
    created_at = db.Column(SafeDateTime, default=wib_now)

    def set_password(self, raw: str):
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw: str) -> bool:
        if not self.password_hash or not raw:
            return False
        if self.password_hash == raw:
            self.set_password(raw)
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
            return True
        try:
            return check_password_hash(self.password_hash, raw)
        except Exception:
            return False

    @property
    def school_name(self):
        return self.school.name if self.school else "SMK Telkom Bandung"


class Student(db.Model):
    __tablename__ = "students"
    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.Integer, db.ForeignKey("schools.id"), nullable=True)
    nis = db.Column(db.String(20), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    class_name = db.Column(db.String(20), nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    password_version = db.Column(db.Integer, default=1, nullable=False)
    phone = db.Column(db.String(20))
    avatar_path = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(SafeDateTime, default=wib_now)

    borrowings = db.relationship("Borrowing", backref="student", lazy=True)

    def set_password(self, raw: str):
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw: str) -> bool:
        if not self.password_hash or not raw:
            return False
        if self.password_hash == raw:
            self.set_password(raw)
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
            return True
        try:
            return check_password_hash(self.password_hash, raw)
        except Exception:
            return False

    @property
    def school_name(self):
        return self.school.name if self.school else "SMK Telkom Bandung"

    @property
    def avatar_url(self):
        if self.avatar_path:
            from flask import url_for
            relative = self.avatar_path.replace("\\", "/")
            if relative.startswith("static/"):
                relative = relative[7:]
            return url_for('static', filename=relative, _external=False)
        return None

    @property
    def active_borrowings_count(self):
        return Borrowing.query.filter_by(student_id=self.id, status="active").count()


class Tool(db.Model):
    __tablename__ = "tools"
    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.Integer, db.ForeignKey("schools.id"), nullable=True)
    code = db.Column(db.String(30), nullable=False, index=True)  # MTR-001
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50))                                        # Multimeter, ESP32, dll
    lab_location = db.Column(db.String(50))                                    # Rak A3
    condition = db.Column(db.String(20), default="Baik")                       # Baik / Rusak Ringan / Rusak Berat
    description = db.Column(db.Text)
    photo_emoji = db.Column(db.String(10), default="🔧")                        # placeholder visual
    qr_path = db.Column(db.String(200))                                         # static/qr_codes/MTR-001.png
    icon = db.Column(db.String(10), default="📦")                              # visual icon
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(SafeDateTime, default=wib_now)

    borrowings = db.relationship("Borrowing", backref="tool", lazy=True)

    @property
    def qr_url(self):
        """Public URL to this tool's QR code image."""
        if self.qr_path:
            from flask import url_for
            relative = self.qr_path.replace("\\", "/")
            if relative.startswith("static/"):
                relative = relative[7:]
            return url_for('static', filename=relative, _external=False)
        return None

    @property
    def active_borrowings_count(self):
        return Borrowing.query.filter_by(tool_id=self.id, status="active").count()

    def current_borrowing(self):
        """Return the active borrowing row (not yet returned), or None."""
        return (
            Borrowing.query.filter_by(tool_id=self.id, status="active")
            .order_by(Borrowing.borrow_date.desc())
            .first()
        )

    def is_available(self) -> bool:
        return self.current_borrowing() is None and self.is_active

    @property
    def school_name(self):
        return self.school.name if self.school else "SMK Telkom Bandung"


class Borrowing(db.Model):
    __tablename__ = "borrowings"
    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.Integer, db.ForeignKey("schools.id"), nullable=True)
    tool_id = db.Column(db.Integer, db.ForeignKey("tools.id"), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=True)
    archived_student_name = db.Column(db.String(100))
    archived_student_nis = db.Column(db.String(20))
    borrow_date = db.Column(SafeDateTime, default=wib_now)
    deadline = db.Column(SafeDateTime, nullable=False)
    return_date = db.Column(SafeDateTime)
    status = db.Column(db.String(20), default="active")   # active / returned / overdue
    condition_after = db.Column(db.String(20))
    notes = db.Column(db.Text)
    force_returned = db.Column(db.Boolean, default=False)
    extend_count = db.Column(db.Integer, default=0)

    @property
    def student_name(self):
        return self.student.name if self.student else (self.archived_student_name or "(murid dihapus)")

    @property
    def student_nis(self):
        return self.student.nis if self.student else (self.archived_student_nis or "-")

    @property
    def student_avatar_url(self):
        return self.student.avatar_url if self.student else None

    @property
    def student_initial(self):
        name = self.student_name
        return name[0].upper() if name and name[0].isalpha() else "?"
    
    @property
    def tool_name(self):
        return self.tool.name if self.tool else ""
    
    @property
    def tool_code(self):
        return self.tool.code if self.tool else ""
    
    @property
    def start_time(self):
        return self.borrow_date
    
    @property
    def due_time(self):
        return self.deadline
    
    @property
    def return_time(self):
        return self.return_date

    @staticmethod
    def default_deadline_hours(school_id=None) -> int:
        if school_id:
            sch = School.query.get(school_id)
            if sch and getattr(sch, 'loan_duration_hours', None):
                return sch.loan_duration_hours
        cfg = Config.get_solo()
        return cfg.loan_duration_hours if cfg else 2

    def seconds_remaining(self) -> int:
        delta = self.deadline - wib_now()
        return int(delta.total_seconds())

    def is_overdue(self) -> bool:
        return self.seconds_remaining() < 0

    def elapsed_seconds(self) -> int:
        delta = wib_now() - self.borrow_date
        return int(delta.total_seconds())


class Config(db.Model):
    """Singleton row (id=1) — runtime settings admin can change."""
    __tablename__ = "config"
    id = db.Column(db.Integer, primary_key=True)
    loan_duration_hours = db.Column(db.Integer, default=2)
    school_name = db.Column(db.String(100), default="SMK Telkom Bandung")
    base_url = db.Column(db.String(200), default="http://localhost:5000")

    @classmethod
    def get_solo(cls):
        return cls.query.get(1)


def init_db(app):
    """Create tables and seed initial default schools if missing."""
    db.init_app(app)
    with app.app_context():
        db.create_all()

        # Auto-migrate loan_duration_hours column in schools table if missing
        try:
            db.session.execute(db.text("ALTER TABLE schools ADD COLUMN loan_duration_hours INTEGER DEFAULT 2"))
            db.session.commit()
        except Exception:
            db.session.rollback()
        
        # Seed default schools if empty
        if School.query.count() == 0:
            default_schools = [
                School(id=1, code="TELKOM-BDG", name="SMK Telkom Bandung", address="Jl. Terusan Buah Batu No. 33"),
                School(id=2, code="SMKN1-JKT", name="SMK Negeri 1 Jakarta", address="Jl. Budi Utomo No. 7"),
                School(id=3, code="SMAN3-SBY", name="SMA Negeri 3 Surabaya", address="Jl. Memet Sastrawidjaja"),
            ]
            db.session.add_all(default_schools)
            db.session.commit()

        if Config.get_solo() is None:
            db.session.add(Config(id=1, loan_duration_hours=2, school_name="SMK Telkom Bandung",
                                  base_url="http://localhost:5000"))
            db.session.commit()

        # Seed default admin if empty
        if Admin.query.count() == 0:
            default_admin = Admin(school_id=1, username="admin", full_name="Administrator Lab")
            default_admin.set_password("admin123")
            db.session.add(default_admin)
            db.session.commit()

        # Seed default students for all schools if empty
        if Student.query.count() == 0:
            sample_students = [
                ("1001", "Budi Santoso", "XII RPL 1"),
                ("1002", "Siti Nurhaliza", "XII RPL 1"),
                ("1003", "Ahmad Dahlan", "XII TKJ 2"),
                ("1004", "Dewi Sartika", "XI RPL 2"),
                ("1005", "Eko Prasetyo", "X TJA 1"),
            ]
            for school in School.query.all():
                for nis, name, cls in sample_students:
                    st = Student(school_id=school.id, nis=nis, name=name, class_name=cls)
                    st.set_password("siswa123")
                    db.session.add(st)
            db.session.commit()

        # Update existing null school_ids to default school (id=1)
        Admin.query.filter(Admin.school_id == None).update({Admin.school_id: 1})
        Student.query.filter(Student.school_id == None).update({Student.school_id: 1})
        Tool.query.filter(Tool.school_id == None).update({Tool.school_id: 1})
        Borrowing.query.filter(Borrowing.school_id == None).update({Borrowing.school_id: 1})
        db.session.commit()

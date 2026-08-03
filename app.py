import sys
import os

# Fix: Ensure this project's venv site-packages comes FIRST in sys.path
_this_dir = os.path.dirname(os.path.abspath(__file__))
_venv_site = os.path.join(_this_dir, 'venv', 'Lib', 'site-packages')
if _venv_site in sys.path:
    sys.path.remove(_venv_site)
sys.path.insert(0, _venv_site)

"""LabKeeper — Main Flask application
Multi-School Lab Equipment Borrowing System with QR Codes.
- Dual entry portals on landing page: Student Portal & School/Admin Portal
- Student login with "Asal Sekolah" dropdown selection
- Admin manages equipment, students, and borrowings strictly isolated per school
"""
import os
from datetime import datetime, timedelta, timezone
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from dotenv import load_dotenv


def utcnow() -> datetime:
    """Timezone-aware UTC now (Python 3.12+ deprecates naive datetime.utcnow())."""
    return datetime.now(timezone.utc).replace(tzinfo=None)

from models import db, init_db, Student, Admin, Tool, Borrowing, Config, School
from datetime_utils import get_config
from auth import current_student, current_admin, student_required, admin_required
from qr_utils import generate_qr_for_tool, qr_url_for_tool


def create_app() -> Flask:
    load_dotenv()
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "labkeeper-dev-secret-change-me")
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///labkeeper.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=30)  # session persist 30 hari

    init_db(app)

    # ============= SESSION PERSISTENCE =============
    @app.before_request
    def make_session_permanent():
        if session.get("student_id") or session.get("admin_id"):
            session.permanent = True

    # ============= CONTEXT PROCESSORS =============
    @app.context_processor
    def inject_globals():
        import datetime
        import random
        timestamp = int(datetime.datetime.now().timestamp())
        c_student = current_student()
        c_admin = current_admin()
        schools = School.query.filter_by(is_active=True).order_by(School.name).all()
        return {
            "current_student": c_student,
            "current_admin": c_admin,
            "schools": schools,
            "get_config": get_config,
            "now": utcnow,
            "timestamp": timestamp,
            "random_int": random.randint(10000, 99999),
        }

    # ============= PUBLIC ROUTES (no login) =============
    @app.route("/")
    def index():
        c_student = current_student()
        c_admin = current_admin()
        if c_student:
            return redirect(url_for("student_dashboard"))
        if c_admin:
            return redirect(url_for("admin_dashboard"))

        schools = School.query.filter_by(is_active=True).order_by(School.name).all()
        selected_school_id = schools[0].id if schools else 1
        selected_school = School.query.get(selected_school_id) or (schools[0] if schools else None)

        tools = Tool.query.filter_by(is_active=True, school_id=selected_school_id).order_by(Tool.code).all()
        total_alat = len(tools)
        tersedia = sum(1 for t in tools if t.is_available())
        dipinjam = sum(1 for t in tools if not t.is_available())
        categories = sorted(list(set(t.category for t in tools if t.category)))
        
        return render_template(
            "index.html", 
            tools=tools, 
            total_alat=total_alat, 
            tersedia=tersedia, 
            dipinjam=dipinjam, 
            categories=categories, 
            schools=schools,
            selected_school_id=selected_school_id,
            selected_school=selected_school,
            base_url=get_config().base_url
        )

    @app.route("/tool/<code>")
    def tool_detail(code):
        tool = Tool.query.filter_by(code=code, is_active=True).first()
        if not tool:
            flash(f"Alat dengan kode '{code}' tidak ditemukan di sistem LabKeeper.", "error")
            return redirect(url_for("scan"))
        current = tool.current_borrowing()
        student = current_student()
        history = Borrowing.query.filter_by(tool_id=tool.id).order_by(Borrowing.borrow_date.desc()).limit(20).all()
        return render_template("tool_detail.html", tool=tool, current=current, student=student, borrowing_history=history, base_url=get_config().base_url)

    @app.route("/scan")
    def scan():
        """In-browser QR scanner page for mobile devices."""
        code = request.args.get("code", "").strip().upper()
        tool = None
        if code:
            tool = Tool.query.filter_by(code=code, is_active=True).first()
        return render_template("scan.html", tool=tool)

    # Unified login entry point
    @app.route("/login")
    def login():
        if current_admin():
            return redirect(url_for("admin_dashboard"))
        if current_student():
            return redirect(url_for("student_dashboard"))
        return redirect(url_for("student_login"))

    # ============= STUDENT AUTH + ACTIONS =============
    @app.route("/student/login", methods=["GET", "POST"])
    def student_login():
        if current_admin():
            return redirect(url_for("admin_dashboard"))
        if current_student():
            return redirect(url_for("student_dashboard"))
        
        schools = School.query.filter_by(is_active=True).order_by(School.name).all()
        nxt = request.args.get("next") or url_for("index")
        
        if request.method == "POST":
            school_id = request.form.get("school_id")
            nis = request.form.get("nis", "").strip()
            password = request.form.get("password", "")
            
            if not school_id or not nis or not password:
                flash("Pilih asal sekolah, NIS, dan password wajib diisi.", "warning")
                return render_template("login.html", schools=schools, next_url=nxt)

            student = Student.query.filter_by(school_id=school_id, nis=nis).first()
            
            if student and not student.is_active:
                flash("Akun Anda sudah dinonaktifkan. Hubungi admin lab sekolah.", "error")
            elif student and student.check_password(password):
                session.permanent = True
                session["student_id"] = student.id
                session["school_id"] = student.school_id
                flash(f"Selamat datang, {student.name} ({student.school_name})!", "success")
                return redirect(request.form.get("next") or nxt)
            else:
                flash("Sekolah, NIS, atau password salah.", "error")
                
        return render_template("login.html", schools=schools, next_url=nxt)

    @app.route("/student/dashboard")
    @student_required
    def student_dashboard():
        student = current_student()
        
        # Only fetch active and past borrowings for this specific student
        active = Borrowing.query.filter_by(
            student_id=student.id, status="active"
        ).order_by(Borrowing.borrow_date.desc()).all()
        past = Borrowing.query.filter(
            Borrowing.student_id == student.id,
            Borrowing.status.in_(["returned", "overdue"])
        ).order_by(Borrowing.borrow_date.desc()).limit(50).all()
        active_borrowing = active[0] if active else None
        
        return render_template(
            "student_dashboard.html",
            student=student,
            active_borrowing=active_borrowing,
            active_list=active,
            past=past,
            base_url=get_config().base_url
        )

    @app.route("/katalog")
    @student_required
    def student_catalog():
        student = current_student()
        school_id = student.school_id or 1
        
        tools = Tool.query.filter_by(school_id=school_id, is_active=True).order_by(Tool.code).all()
        total_alat = len(tools)
        tersedia = sum(1 for t in tools if t.is_available())
        dipinjam = sum(1 for t in tools if not t.is_available())
        categories = sorted(list(set(t.category for t in tools if t.category)))
        
        return render_template(
            "student_catalog.html",
            student=student,
            tools=tools,
            total_alat=total_alat,
            tersedia=tersedia,
            dipinjam=dipinjam,
            categories=categories,
            base_url=get_config().base_url
        )

    @app.route("/student/profile", methods=["GET", "POST"])
    @student_required
    def student_profile():
        student = current_student()
        if request.method == "POST":
            # 1. Password Update
            old_password = request.form.get("old_password", "")
            new_password = request.form.get("new_password", "")
            confirm_password = request.form.get("confirm_password", "")

            if old_password or new_password or confirm_password:
                if not student.check_password(old_password):
                    flash("Password lama yang Anda masukkan salah.", "error")
                    return redirect(url_for("student_profile"))
                if len(new_password) < 4:
                    flash("Password baru minimal 4 karakter.", "warning")
                    return redirect(url_for("student_profile"))
                if new_password != confirm_password:
                    flash("Konfirmasi password baru tidak cocok.", "error")
                    return redirect(url_for("student_profile"))
                
                student.set_password(new_password)
                flash("Password Anda berhasil diperbarui!", "success")

            # 2. Profile Photo Avatar Upload
            if "avatar" in request.files:
                file = request.files["avatar"]
                if file and file.filename != "":
                    ext = os.path.splitext(file.filename)[1].lower()
                    if ext in [".jpg", ".jpeg", ".png", ".webp", ".gif"]:
                        os.makedirs("static/uploads/avatars", exist_ok=True)
                        filename = f"avatar_std_{student.id}_{int(utcnow().timestamp())}{ext}"
                        filepath = os.path.join("static/uploads/avatars", filename)
                        file.save(filepath)
                        student.avatar_path = filepath
                        flash("Foto profil berhasil diperbarui!", "success")
                    else:
                        flash("Format foto harus JPG, PNG, WEBP, atau GIF.", "error")

            db.session.commit()
            return redirect(url_for("student_profile"))

        return render_template("student_profile.html", student=student)

    @app.route("/logout")
    def logout():
        session.clear()
        flash("Anda sudah logout.", "info")
        return redirect(url_for("index"))

    @app.route("/clear-flash")
    def clear_flash():
        from flask import session as fl_session
        fl_session.pop("_flashes", None)
        return redirect(request.referrer or url_for("index"))

    @app.route("/pinjam/<code>", methods=["GET", "POST"])
    @student_required
    def pinjam(code):
        tool = Tool.query.filter_by(code=code, is_active=True).first_or_404()
        student = current_student()
        
        # Enforce same school check
        if tool.school_id and student.school_id and tool.school_id != student.school_id:
            flash(f"Alat ini milik laboratorium {tool.school_name}. Anda terdaftar di {student.school_name}.", "error")
            return redirect(url_for("tool_detail", code=code))

        if not tool.is_available():
            flash(f"Maaf, {tool.name} sedang dipinjam.", "warning")
            return redirect(url_for("tool_detail", code=code))

        if request.method == "POST":
            notes = request.form.get("notes", "").strip()
            hours = get_config().loan_duration_hours
            new = Borrowing(
                school_id=student.school_id or tool.school_id,
                tool_id=tool.id,
                student_id=student.id,
                borrow_date=utcnow(),
                deadline=utcnow() + timedelta(hours=hours),
                notes=notes,
            )
            db.session.add(new)
            db.session.commit()
            flash(f"Berhasil meminjam {tool.name}. Kembalikan sebelum {new.deadline.strftime('%H:%M')}.", "success")
            return redirect(url_for("tool_detail", code=code))

        hours = get_config().loan_duration_hours
        return render_template("pinjam.html", tool=tool, duration_hours=hours)

    @app.route("/kembalikan/<code>", methods=["POST"])
    @student_required
    def kembalikan(code):
        tool = Tool.query.filter_by(code=code, is_active=True).first_or_404()
        student = current_student()
        current = tool.current_borrowing()
        if current is None:
            flash("Alat ini tidak sedang dipinjam.", "warning")
            return redirect(url_for("tool_detail", code=code))
        if current.student_id != student.id:
            flash("Alat ini dipinjam oleh siswa lain. Hubungi laboran jika perlu.", "error")
            return redirect(url_for("tool_detail", code=code))
        current.return_date = utcnow()
        current.status = "returned"
        current.condition_after = request.form.get("condition_after", "Baik")
        db.session.commit()
        flash(f"Terima kasih! {tool.name} sudah dikembalikan.", "success")
        return redirect(request.referrer or url_for("student_dashboard"))

    @app.route("/perpanjang/<int:borrowing_id>", methods=["GET", "POST"])
    @student_required
    def perpanjang(borrowing_id):
        borrowing = Borrowing.query.get_or_404(borrowing_id)
        student = current_student()
        if borrowing.student_id != student.id:
            flash("Anda tidak memiliki akses ke peminjaman ini.", "error")
            return redirect(url_for("student_dashboard"))
        if borrowing.status == "returned":
            flash("Peminjaman ini sudah selesai.", "warning")
            return redirect(url_for("student_dashboard"))
        
        max_extends = 2
        extend_count = getattr(borrowing, 'extend_count', 0)
        if extend_count >= max_extends:
            flash("Batas perpanjangan sudah tercapai (maksimal 2 kali).", "warning")
            return redirect(url_for("student_dashboard"))
        
        if request.method == "POST":
            choice = request.form.get("choice")
            if choice == "return":
                borrowing.return_date = utcnow()
                borrowing.status = "returned"
                db.session.commit()
                flash(f"{borrowing.tool.name} berhasil dikembalikan.", "success")
                return redirect(url_for("student_dashboard"))
            elif choice == "extend":
                hours = get_config().loan_duration_hours
                borrowing.deadline = borrowing.deadline + timedelta(hours=hours)
                borrowing.extend_count = extend_count + 1
                db.session.commit()
                new_deadline = borrowing.deadline.strftime('%d/%m/%Y %H:%M')
                flash(f"Peminjaman {borrowing.tool.name} diperpanjang hingga {new_deadline}.", "success")
                return redirect(url_for("student_dashboard"))
        
        can_extend = extend_count < max_extends
        return render_template(
            "extend_confirm.html",
            borrowing=borrowing,
            loan_duration_hours=get_config().loan_duration_hours,
            can_extend=can_extend,
            extend_count=extend_count,
            max_extends=max_extends
        )

    @app.route("/riwayat")
    @student_required
    def my_history():
        student = current_student()
        borrowings = (Borrowing.query.filter_by(student_id=student.id)
                      .order_by(Borrowing.borrow_date.desc()).limit(50).all())
        return render_template("history.html", borrowings=borrowings)

    @app.route("/admin/login", methods=["GET", "POST"])
    def admin_login():
        if current_admin():
            return redirect(url_for("admin_dashboard"))
        nxt = request.args.get("next") or url_for("admin_dashboard")
        schools = School.query.filter_by(is_active=True).order_by(School.name).all()
        if request.method == "POST":
            school_id = request.form.get("school_id")
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            
            if not school_id or not username or not password:
                flash("Pilih asal sekolah, username, dan password wajib diisi.", "warning")
                return render_template("admin/admin_login.html", schools=schools, next_url=nxt)

            admin = Admin.query.filter_by(school_id=school_id, username=username).first()
            if not admin:
                admin = Admin.query.filter_by(username=username).first()

            if admin and admin.check_password(password):
                session.permanent = True
                session["admin_id"] = admin.id
                session["school_id"] = admin.school_id
                flash(f"Login berhasil. Halo, {admin.full_name or admin.username} ({admin.school_name}).", "success")
                return redirect(request.form.get("next") or nxt)
            flash("Sekolah, username, atau password salah.", "error")
        return render_template("admin/admin_login.html", schools=schools, next_url=nxt)

    @app.route("/admin/logout")
    def admin_logout():
        session.pop("admin_id", None)
        flash("Anda sudah logout.", "info")
        return redirect(url_for("index"))

    @app.route("/admin/dashboard")
    @admin_required
    def admin_dashboard():
        admin = current_admin()
        school_id = admin.school_id or 1
        
        active_query = Borrowing.query.filter_by(status="active")
        if school_id:
            active_query = active_query.filter_by(school_id=school_id)
        active = active_query.order_by(Borrowing.deadline.asc()).all()

        for b in active:
            b.seconds_left = b.seconds_remaining()
            b.elapsed_str = _humanize_seconds(b.elapsed_seconds())
            b.remaining_str = _humanize_seconds(b.seconds_left)

        tools_query = Tool.query.filter_by(is_active=True)
        if school_id:
            tools_query = tools_query.filter_by(school_id=school_id)
        all_tools = tools_query.all()

        total_alat = len(all_tools)
        tersedia = sum(1 for t in all_tools if t.is_available())
        dipinjam = sum(1 for t in all_tools if not t.is_available())
        telat = sum(1 for b in active if b.is_overdue)

        recent_query = Borrowing.query
        if school_id:
            recent_query = recent_query.filter_by(school_id=school_id)
        recent_borrowings = recent_query.order_by(Borrowing.borrow_date.desc()).limit(20).all()

        return render_template(
            "admin/dashboard.html", 
            total_alat=total_alat, 
            tersedia=tersedia, 
            dipinjam=dipinjam, 
            telat=telat,
            recent_borrowings=recent_borrowings,
            admin=admin
        )

    @app.route("/admin/tools")
    @admin_required
    def admin_tools():
        admin = current_admin()
        school_id = admin.school_id or 1
        search = request.args.get("search", "").strip()
        action = request.args.get("action", "")
        
        if action == "add":
            return render_template("admin/tool_form.html", tool=None, admin=admin)
        
        if action == "edit":
            code = request.args.get("code", "")
            tool = Tool.query.filter_by(code=code, school_id=school_id).first_or_404()
            return render_template("admin/tool_form.html", tool=tool, admin=admin)
        
        page = int(request.args.get("page", 1))
        per_page = 20
        query = Tool.query.filter_by(is_active=True, school_id=school_id)
        if search:
            query = query.filter(Tool.name.ilike(f"%{search}%") | Tool.code.ilike(f"%{search}%"))
        total = query.count()
        tools = query.order_by(Tool.code).offset((page - 1) * per_page).limit(per_page).all()
        total_pages = max(1, (total + per_page - 1) // per_page)
        return render_template("admin/tools.html", tools=tools, search=search, current_page=page, total_pages=total_pages, admin=admin)
    
    @app.route("/admin/tools/action", methods=["POST"])
    @admin_required
    def admin_tools_action():
        admin = current_admin()
        school_id = admin.school_id or 1
        action = request.form.get("_action", "add")
        
        if action == "add":
            code = request.form.get("code", "").strip().upper()
            name = request.form.get("name", "").strip()
            category = request.form.get("category", "").strip()
            lab_location = request.form.get("lab_location", "").strip()
            condition = request.form.get("condition", "Baik")
            description = request.form.get("description", "").strip()
            icon = request.form.get("icon", "📦").strip()
            
            if not code or not name:
                flash("Kode dan nama alat wajib diisi.", "error")
                return redirect(url_for("admin_tools"))
            if Tool.query.filter_by(code=code, school_id=school_id).first():
                flash(f"Kode {code} sudah dipakai di sekolah ini.", "error")
                return redirect(url_for("admin_tools"))
            
            tool = Tool(
                school_id=school_id, 
                code=code, 
                name=name, 
                category=category, 
                lab_location=lab_location, 
                condition=condition, 
                description=description, 
                icon=icon
            )
            db.session.add(tool)
            db.session.commit()
            try:
                qr_path = generate_qr_for_tool(tool)
                tool.qr_path = qr_path
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                flash(f"Alat ditambahkan tapi QR gagal di-generate: {e}", "warning")
            flash(f"Alat {tool.name} ditambahkan.", "success")
            return redirect(url_for("admin_tools"))
        
        elif action == "update":
            old_code = request.form.get("old_code", "").strip().upper()
            tool = Tool.query.filter_by(code=old_code, school_id=school_id).first_or_404()
            new_code = request.form.get("code", "").strip().upper()
            tool.code = new_code
            tool.name = request.form.get("name", "").strip()
            tool.category = request.form.get("category", "").strip()
            tool.lab_location = request.form.get("lab_location", "").strip()
            tool.condition = request.form.get("condition", "Baik")
            tool.description = request.form.get("description", "").strip()
            tool.icon = request.form.get("icon", "📦").strip()
            db.session.commit()
            flash(f"Data {tool.name} diperbarui.", "success")
            return redirect(url_for("admin_tools"))
        
        elif action == "delete":
            code = request.form.get("code", "").strip().upper()
            if not code:
                code = request.form.get("id", "").strip().upper()
            tool = Tool.query.filter_by(code=code, school_id=school_id).first_or_404()
            if tool.current_borrowing():
                flash("Tidak bisa hapus alat yang sedang dipinjam.", "error")
            else:
                tool.is_active = False
                db.session.commit()
                flash(f"Alat {tool.name} dihapus.", "info")
            return redirect(url_for("admin_tools"))
        
        return redirect(url_for("admin_tools"))

    @app.route("/admin/generate-qr/<code>", methods=["POST"])
    @admin_required
    def admin_generate_qr(code):
        admin = current_admin()
        school_id = admin.school_id or 1
        tool = Tool.query.filter_by(code=code, school_id=school_id, is_active=True).first_or_404()
        path = generate_qr_for_tool(tool)
        tool.qr_path = path
        db.session.commit()
        return jsonify({"success": True, "qr_code": tool.qr_url})

    @app.route("/admin/generate-all-qr")
    @admin_required
    def admin_generate_all_qr():
        admin = current_admin()
        school_id = admin.school_id or 1
        tools = Tool.query.filter_by(school_id=school_id, is_active=True).all()
        for tool in tools:
            generate_qr_for_tool(tool)
        db.session.commit()
        flash(f"QR code berhasil di-generate untuk {len(tools)} alat.", "success")
        return redirect(url_for("admin_qr_labels"))

    @app.route("/admin/borrowings")
    @admin_required
    def admin_borrowings():
        admin = current_admin()
        school_id = admin.school_id or 1
        search = request.args.get("search", "").strip()
        status_filter = request.args.get("status_filter", "").strip()
        
        q = Borrowing.query.filter_by(school_id=school_id).order_by(Borrowing.borrow_date.desc())
        if search:
            q = q.filter(
                db.or_(
                    Borrowing.student_name.ilike(f"%{search}%"),
                    Borrowing.tool_name.ilike(f"%{search}%"),
                    Borrowing.tool_code.ilike(f"%{search}%"),
                )
            )
        if status_filter == "active":
            q = q.filter_by(status="active")
        elif status_filter == "returned":
            q = q.filter_by(status="returned")
        elif status_filter == "overdue":
            q = q.filter_by(status="active").filter(Borrowing.deadline < utcnow())
        borrowings = q.limit(100).all()
        for b in borrowings:
            b.seconds_left = b.seconds_remaining()
        return render_template("admin/borrowings.html", borrowings=borrowings, 
                               search=search, status_filter=status_filter, admin=admin)

    @app.route("/admin/borrowings/export-csv")
    @admin_required
    def admin_export_borrowings_csv():
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter
        from io import BytesIO
        from flask import send_file

        admin = current_admin()
        school_id = admin.school_id or 1
        search = request.args.get("search", "").strip()
        status_filter = request.args.get("status_filter", "").strip()

        q = Borrowing.query.filter_by(school_id=school_id).order_by(Borrowing.borrow_date.desc())
        if search:
            q = q.filter(
                db.or_(
                    Borrowing.student_name.ilike(f"%{search}%"),
                    Borrowing.tool_name.ilike(f"%{search}%"),
                    Borrowing.tool_code.ilike(f"%{search}%"),
                )
            )
        if status_filter == "active":
            q = q.filter_by(status="active")
        elif status_filter == "returned":
            q = q.filter_by(status="returned")
        elif status_filter == "overdue":
            q = q.filter_by(status="active").filter(Borrowing.deadline < utcnow())

        borrowings = q.all()

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Laporan Peminjaman"
        ws.views.sheetView[0].showGridLines = True

        title_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
        subtitle_fill = PatternFill(start_color="334155", end_color="334155", fill_type="solid")
        header_fill = PatternFill(start_color="0F172A", end_color="0F172A", fill_type="solid")
        even_row_fill = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")
        odd_row_fill = PatternFill(start_color="FFFFFF", end_color="FFFFFF", fill_type="solid")

        status_returned_fill = PatternFill(start_color="DCFCE7", end_color="DCFCE7", fill_type="solid")
        status_returned_font = Font(name="Segoe UI", size=10, bold=True, color="15803D")

        status_overdue_fill = PatternFill(start_color="FEE2E2", end_color="FEE2E2", fill_type="solid")
        status_overdue_font = Font(name="Segoe UI", size=10, bold=True, color="B91C1C")

        status_active_fill = PatternFill(start_color="DBEAFE", end_color="DBEAFE", fill_type="solid")
        status_active_font = Font(name="Segoe UI", size=10, bold=True, color="1D4ED8")

        title_font = Font(name="Segoe UI", size=14, bold=True, color="FFFFFF")
        subtitle_font = Font(name="Segoe UI", size=10, italic=True, color="E2E8F0")
        header_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
        body_font = Font(name="Segoe UI", size=10, color="0F172A")

        thin_border = Border(
            left=Side(style='thin', color='CBD5E1'),
            right=Side(style='thin', color='CBD5E1'),
            top=Side(style='thin', color='CBD5E1'),
            bottom=Side(style='thin', color='CBD5E1')
        )

        align_center = Alignment(horizontal="center", vertical="center")
        align_left = Alignment(horizontal="left", vertical="center")

        ws.merge_cells("A1:K1")
        ws["A1"] = f"LAPORAN REKAPITULASI PEMINJAMAN ALAT — {admin.school_name.upper()}"
        ws["A1"].font = title_font
        ws["A1"].fill = title_fill
        ws["A1"].alignment = align_center
        ws.row_dimensions[1].height = 32

        ws.merge_cells("A2:K2")
        now_str = utcnow().strftime("%d/%m/%Y %H:%M WIB")
        ws["A2"] = f"Sistem LabKeeper — {admin.school_name}  |  Tanggal Cetak: {now_str}  |  Total Data: {len(borrowings)}"
        ws["A2"].font = subtitle_font
        ws["A2"].fill = subtitle_fill
        ws["A2"].alignment = align_center
        ws.row_dimensions[2].height = 22

        ws.row_dimensions[3].height = 10

        headers = ["No", "ID", "Nama Siswa", "NIS", "Kode Alat", "Nama Alat", "Tgl Pinjam", "Batas Kembali", "Tgl Kembali", "Status", "Kondisi Akhir"]
        ws.row_dimensions[4].height = 26

        for col_idx, text in enumerate(headers, 1):
            cell = ws.cell(row=4, column=col_idx, value=text)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = align_center
            cell.border = thin_border

        start_row = 5
        for idx, b in enumerate(borrowings, 1):
            row_num = start_row + idx - 1
            ws.row_dimensions[row_num].height = 22
            row_fill = even_row_fill if idx % 2 == 0 else odd_row_fill

            is_returned = bool(b.return_time)
            is_overdue = b.is_overdue() if hasattr(b, 'is_overdue') else False
            status_str = "Dikembalikan" if is_returned else ("Telat" if is_overdue else "Aktif")

            row_data = [
                (idx, align_center),
                (f"#{b.id}", align_center),
                (b.student_name or "-", align_left),
                (b.student_nis or "-", align_center),
                (b.tool_code or "-", align_center),
                (b.tool_name or "-", align_left),
                (b.start_time.strftime("%d/%m/%Y %H:%M") if b.start_time else "-", align_center),
                (b.due_time.strftime("%d/%m/%Y %H:%M") if b.due_time else "-", align_center),
                (b.return_time.strftime("%d/%m/%Y %H:%M") if b.return_time else "-", align_center),
                (status_str, align_center),
                (b.condition_after or "Baik", align_center),
            ]

            for col_idx, (val, alignment) in enumerate(row_data, 1):
                cell = ws.cell(row=row_num, column=col_idx, value=val)
                cell.font = body_font
                cell.fill = row_fill
                cell.alignment = alignment
                cell.border = thin_border

                if col_idx == 10:
                    if status_str == "Dikembalikan":
                        cell.fill = status_returned_fill
                        cell.font = status_returned_font
                    elif status_str == "Telat":
                        cell.fill = status_overdue_fill
                        cell.font = status_overdue_font
                    else:
                        cell.fill = status_active_fill
                        cell.font = status_active_font

        padding = {1: 6, 2: 8, 3: 24, 4: 14, 5: 14, 6: 24, 7: 20, 8: 20, 9: 20, 10: 16, 11: 16}
        for col_idx, width in padding.items():
            col_letter = get_column_letter(col_idx)
            ws.column_dimensions[col_letter].width = width

        output = BytesIO()
        wb.save(output)
        output.seek(0)

        filename = f"laporan_peminjaman_{utcnow().strftime('%Y%m%d_%H%M')}.xlsx"
        return send_file(
            output,
            as_attachment=True,
            download_name=filename,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    @app.route("/admin/return/<int:bid>", methods=["GET", "POST"])
    @admin_required
    def admin_return(bid):
        admin = current_admin()
        school_id = admin.school_id or 1
        b = Borrowing.query.filter_by(id=bid, school_id=school_id).first_or_404()
        if request.method == "POST":
            b.return_date = utcnow()
            b.status = "returned"
            b.condition_after = request.form.get("condition_after", "Baik")
            db.session.commit()
            flash(f"{b.tool_name} dikembalikan oleh {b.student_name}.", "success")
            return redirect(request.referrer or url_for("admin_borrowings"))
        return redirect(request.referrer or url_for("admin_borrowings"))

    @app.route("/admin/extend/<int:bid>", methods=["GET", "POST"])
    @admin_required
    def admin_extend(bid):
        admin = current_admin()
        school_id = admin.school_id or 1
        b = Borrowing.query.filter_by(id=bid, school_id=school_id).first_or_404()
        if b.status == "returned":
            flash("Peminjaman sudah dikembalikan.", "warning")
            return redirect(url_for("admin_borrowings"))
        try:
            hours = int(request.form.get("hours", 2)) if request.method == "POST" else int(request.args.get("hours", 2))
        except (TypeError, ValueError):
            hours = 2
        hours = max(1, min(hours, 168))

        base = b.deadline if b.deadline > utcnow() else utcnow()
        b.deadline = base + timedelta(hours=hours)
        b.extend_count = (b.extend_count or 0) + 1
        if b.status == "overdue":
            b.status = "active"
        db.session.commit()
        flash(f"Deadline {b.tool_name} diperpanjang admin +{hours} jam → {b.deadline.strftime('%d/%m/%Y %H:%M')}.", "success")
        return redirect(url_for("admin_borrowings"))

    @app.route("/admin/borrowings/bulk-action", methods=["POST"])
    @admin_required
    def admin_borrowings_bulk_action():
        admin = current_admin()
        school_id = admin.school_id or 1
        action = request.form.get("_action", "")
        bid_list = request.form.getlist("bid")
        try:
            hours = max(1, min(int(request.form.get("hours", 2)), 168))
        except (TypeError, ValueError):
            hours = 2

        if not bid_list:
            flash("Pilih minimal satu peminjaman terlebih dahulu.", "warning")
            return redirect(url_for("admin_borrowings"))

        bid_ints = [int(x) for x in bid_list if x.isdigit()]
        borrowings = Borrowing.query.filter(Borrowing.id.in_(bid_ints), Borrowing.school_id == school_id).all()
        if not borrowings:
            flash("Tidak ada peminjaman yang cocok.", "error")
            return redirect(url_for("admin_borrowings"))

        if action == "return":
            count = 0
            for b in borrowings:
                if b.status != "returned":
                    b.return_date = utcnow()
                    b.status = "returned"
                    b.condition_after = request.form.get("condition_after", "Baik")
                    count += 1
            db.session.commit()
            flash(f"{count} peminjaman ditandai dikembalikan.", "success")

        elif action == "extend":
            count = 0
            for b in borrowings:
                if b.status == "returned":
                    continue
                base = b.deadline if b.deadline > utcnow() else utcnow()
                b.deadline = base + timedelta(hours=hours)
                b.extend_count = (b.extend_count or 0) + 1
                if b.status == "overdue":
                    b.status = "active"
                count += 1
            db.session.commit()
            flash(f"{count} peminjaman diperpanjang +{hours} jam.", "success")
        else:
            flash(f"Aksi tidak dikenal: {action}", "error")

        return redirect(url_for("admin_borrowings"))

    @app.route("/admin/students")
    @admin_required
    def admin_students():
        admin = current_admin()
        school_id = admin.school_id or 1
        search = request.args.get("search", "").strip()
        status_filter = request.args.get("status_filter", "").strip()
        action = request.args.get("action", "")
        
        if action == "add":
            return render_template("admin/student_form.html", student=None, admin=admin)
        
        if action == "edit":
            nis = request.args.get("nis", "")
            student = Student.query.filter_by(nis=nis, school_id=school_id).first_or_404()
            return render_template("admin/student_form.html", student=student, admin=admin)
        
        query = Student.query.filter_by(school_id=school_id)
        if status_filter == "active":
            query = query.filter_by(is_active=True)
        elif status_filter == "inactive":
            query = query.filter_by(is_active=False)

        if search:
            query = query.filter(
                db.or_(
                    Student.name.ilike(f"%{search}%"),
                    Student.nis.ilike(f"%{search}%"),
                    Student.class_name.ilike(f"%{search}%"),
                )
            )
        students = query.order_by(Student.class_name, Student.name).all()
        for s in students:
            s.active_borrowings_count = Borrowing.query.filter_by(
                student_id=s.id, status='active'
            ).count()
        return render_template("admin/students.html", students=students, search=search, status_filter=status_filter, admin=admin)

    @app.route("/admin/students/action", methods=["POST"])
    @admin_required
    def admin_students_action():
        admin = current_admin()
        school_id = admin.school_id or 1
        action = request.form.get("_action", "add")
        
        if action == "add":
            nis = request.form.get("nis", "").strip()
            name = request.form.get("name", "").strip()
            class_name = request.form.get("class", "").strip()
            password = request.form.get("password", "").strip()
            
            if not nis or not name or not class_name or not password:
                flash("Semua field wajib diisi.", "error")
                return redirect(url_for("admin_students"))
            if Student.query.filter_by(school_id=school_id, nis=nis).first():
                flash(f"NIS {nis} sudah terdaftar di sekolah ini.", "error")
                return redirect(url_for("admin_students"))
            s = Student(school_id=school_id, nis=nis, name=name, class_name=class_name)
            s.set_password(password)
            db.session.add(s)
            db.session.commit()
            flash(f"Siswa {s.name} ditambahkan.", "success")
            return redirect(url_for("admin_students"))
        
        elif action == "update":
            old_nis = request.form.get("old_nis", "").strip()
            s = Student.query.filter_by(school_id=school_id, nis=old_nis).first_or_404()
            new_nis = request.form.get("nis", "").strip()
            s.nis = new_nis
            s.name = request.form.get("name", "").strip()
            s.class_name = request.form.get("class", "").strip()
            pw = request.form.get("password", "").strip()
            if pw:
                s.set_password(pw)
            db.session.commit()
            flash(f"Siswa {s.name} diperbarui.", "success")
            return redirect(url_for("admin_students"))

        elif action == "delete":
            nis = request.form.get("nis", "").strip()
            s = Student.query.filter_by(school_id=school_id, nis=nis).first_or_404()

            Borrowing.query.filter_by(student_id=s.id).update({
                Borrowing.student_id: None,
                Borrowing.archived_student_name: s.name,
                Borrowing.archived_student_nis: s.nis,
            })

            db.session.delete(s)
            db.session.commit()
            flash(f"Siswa {s.name} dihapus permanen. Histori peminjaman tetap tersimpan.", "info")
            return redirect(url_for("admin_students"))
        
        return redirect(url_for("admin_students"))

    @app.route("/admin/students/bulk-action", methods=["POST"])
    @admin_required
    def admin_students_bulk_action():
        admin = current_admin()
        school_id = admin.school_id or 1
        action = request.form.get("_action", "")
        nis_list = request.form.getlist("nis")

        if not nis_list:
            flash("Pilih minimal satu siswa terlebih dahulu.", "warning")
            return redirect(url_for("admin_students"))

        students = Student.query.filter(Student.nis.in_(nis_list), Student.school_id == school_id).all()
        if not students:
            flash("Tidak ada siswa yang cocok dengan pilihan.", "error")
            return redirect(url_for("admin_students"))

        if action == "activate":
            for s in students:
                s.is_active = True
            db.session.commit()
            flash(f"{len(students)} siswa diaktifkan.", "success")

        elif action == "deactivate":
            for s in students:
                s.is_active = False
            db.session.commit()
            flash(f"{len(students)} siswa dinonaktifkan.", "info")

        elif action == "delete":
            for s in students:
                Borrowing.query.filter_by(student_id=s.id).update({
                    Borrowing.student_id: None,
                    Borrowing.archived_student_name: s.name,
                    Borrowing.archived_student_nis: s.nis,
                })
                db.session.delete(s)
            db.session.commit()
            flash(f"{len(students)} siswa dihapus permanen. Histori peminjaman tetap tersimpan.", "info")
        else:
            flash(f"Aksi tidak dikenal: {action}", "error")

        return redirect(url_for("admin_students"))

    @app.route("/admin/qr-labels")
    @admin_required
    def admin_qr_labels():
        admin = current_admin()
        school_id = admin.school_id or 1
        tools = Tool.query.filter_by(school_id=school_id, is_active=True).order_by(Tool.code).all()
        return render_template("admin/qr_labels.html", tools=tools, admin=admin)

    @app.route("/admin/settings", methods=["GET", "POST"])
    @admin_required
    def admin_settings():
        admin = current_admin()
        cfg = Config.get_solo()
        if request.method == "POST":
            cfg.loan_duration_hours = int(request.form.get("duration_hours", 24))
            db.session.commit()
            flash("Pengaturan disimpan.", "success")
            return redirect(url_for("admin_settings"))
        return render_template("admin/settings.html", settings=cfg, admin=admin)

    @app.route("/admin/reset-borrowings")
    @admin_required
    def admin_reset_borrowings():
        admin = current_admin()
        school_id = admin.school_id or 1
        Borrowing.query.filter_by(school_id=school_id).delete()
        db.session.commit()
        flash(f"Semua riwayat peminjaman {admin.school_name} direset.", "info")
        return redirect(url_for("admin_settings"))

    # ============= JSON API (for live countdown) =============
    @app.route("/api/active-borrowings")
    @admin_required
    def api_active_borrowings():
        admin = current_admin()
        school_id = admin.school_id or 1
        active = Borrowing.query.filter_by(school_id=school_id, status="active").all()
        result = []
        for b in active:
            result.append({
                "id": b.id,
                "tool_code": b.tool.code,
                "tool_name": b.tool.name,
                "student_name": b.student.name if b.student else (b.archived_student_name or "-"),
                "student_nis": b.student.nis if b.student else (b.archived_student_nis or "-"),
                "student_class": b.student.class_name if b.student else "-",
                "elapsed_seconds": b.elapsed_seconds(),
                "remaining_seconds": b.seconds_remaining(),
                "deadline_iso": b.deadline.isoformat() + "Z",
            })
        return jsonify(result)

    return app


def _humanize_seconds(seconds: int) -> str:
    """Convert seconds to a short Indonesian-friendly string."""
    sign = ""
    if seconds < 0:
        sign = "-"
        seconds = abs(seconds)
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    if h > 0:
        return f"{sign}{h}j {m}m"
    if m > 0:
        return f"{sign}{m}m {s}d"
    return f"{sign}{s}d"


# Expose the app for `flask run`
app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

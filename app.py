import sys
import os

# Fix: Ensure this project's venv site-packages comes FIRST in sys.path
# This prevents Hermes venv's corrupt PIL from being imported instead
_this_dir = os.path.dirname(os.path.abspath(__file__))
_venv_site = os.path.join(_this_dir, 'venv', 'Lib', 'site-packages')
if _venv_site in sys.path:
    sys.path.remove(_venv_site)
sys.path.insert(0, _venv_site)

"""LabKeeper — Main Flask application
Lab equipment borrowing system with static QR codes.
- Public visitors can scan a QR (printed on each tool) → land on /tool/<code>
- Students log in (NIS) to actually borrow or return
- Admins (laboran) log in to manage everything
"""
import os
from datetime import datetime, timedelta, timezone
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from dotenv import load_dotenv


def utcnow() -> datetime:
    """Timezone-aware UTC now (Python 3.12+ deprecates naive datetime.utcnow())."""
    return datetime.now(timezone.utc).replace(tzinfo=None)

from models import db, init_db, Student, Admin, Tool, Borrowing, Config
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
    # Make session permanent as long as the user is logged in (student OR admin).
    # This ensures they stay logged in across browser sessions until they explicitly logout.
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
        return {
            "current_student": current_student(),
            "current_admin": current_admin(),
            "get_config": get_config,
            "now": utcnow,
            "timestamp": timestamp,
            "random_int": random.randint(10000, 99999),
        }

    # ============= PUBLIC ROUTES (no login) =============
    @app.route("/")
    def index():
        tools = Tool.query.filter_by(is_active=True).order_by(Tool.code).all()
        total_alat = len(tools)
        tersedia = sum(1 for t in tools if t.is_available())
        dipinjam = sum(1 for t in tools if not t.is_available())
        telat = sum(1 for t in tools if not t.is_available() and t.current_borrowing() and t.current_borrowing().is_overdue())
        categories = sorted(list(set(t.category for t in tools if t.category)))
        return render_template("index.html", tools=tools, total_alat=total_alat, tersedia=tersedia, dipinjam=dipinjam, telat=telat, categories=categories, base_url=get_config().base_url)

    @app.route("/tool/<code>")
    def tool_detail(code):
        tool = Tool.query.filter_by(code=code, is_active=True).first()
        if not tool:
            flash(f"Alat dengan kode '{code}' tidak ditemukan di sistem LabKeeper.", "error")
            return redirect(url_for("scan"))
        current = tool.current_borrowing()
        student = current_student()
        # Get borrowing history for this tool
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

    # Unified login page
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
        nxt = request.args.get("next") or url_for("index")
        if request.method == "POST":
            nis = request.form.get("nis", "").strip()
            password = request.form.get("password", "")
            student = Student.query.filter_by(nis=nis).first()
            if student and not student.is_active:
                flash("Akun Anda sudah dinonaktifkan. Hubungi admin lab.", "error")
            elif student and student.check_password(password):
                session.permanent = True
                session["student_id"] = student.id
                flash(f"Selamat datang, {student.name}!", "success")
                return redirect(request.form.get("next") or nxt)
            flash("NIS atau password salah.", "error")
        return render_template("login.html", next_url=nxt)

    @app.route("/student/dashboard")
    @student_required
    def student_dashboard():
        student = current_student()
        # Get active borrowings for this student
        active = Borrowing.query.filter_by(
            student_id=student.id, status="active"
        ).order_by(Borrowing.borrow_date.desc()).all()
        # Get past borrowings
        past = Borrowing.query.filter(
            Borrowing.student_id == student.id,
            Borrowing.status.in_(["returned", "overdue"])
        ).order_by(Borrowing.borrow_date.desc()).limit(20).all()
        active_borrowing = active[0] if active else None
        return render_template(
            "student_dashboard.html",
            student=student,
            active_borrowing=active_borrowing,
            past=past,
            base_url=get_config().base_url
        )

    @app.route("/logout")
    def logout():
        session.clear()
        flash("Anda sudah logout.", "info")
        return redirect(url_for("index"))

    @app.route("/clear-flash")
    def clear_flash():
        """Clear all flash messages without showing them."""
        from flask import session as fl_session
        fl_session.pop("_flashes", None)
        return redirect(request.referrer or url_for("index"))

    @app.route("/pinjam/<code>", methods=["GET", "POST"])
    @student_required
    def pinjam(code):
        tool = Tool.query.filter_by(code=code, is_active=True).first_or_404()
        student = current_student()
        if not tool.is_available():
            flash(f"Maaf, {tool.name} sedang dipinjam.", "warning")
            return redirect(url_for("tool_detail", code=code))

        if request.method == "POST":
            notes = request.form.get("notes", "").strip()
            hours = get_config().loan_duration_hours
            new = Borrowing(
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
        return redirect(url_for("tool_detail", code=code))

    @app.route("/perpanjang/<int:borrowing_id>", methods=["GET", "POST"])
    @student_required
    def perpanjang(borrowing_id):
        borrowing = Borrowing.query.get_or_404(borrowing_id)
        student = current_student()
        
        # Validasi: hanya bisa perpanjang jika peminjaman milik siswa ini dan masih aktif/telat
        if borrowing.student_id != student.id:
            flash("Anda tidak memiliki izin untuk memperpanjang peminjaman ini.", "error")
            return redirect(url_for("student_dashboard"))
        if borrowing.status == "returned":
            flash("Peminjaman ini sudah selesai.", "warning")
            return redirect(url_for("student_dashboard"))
        
        # Hitung batas perpanjangan maksimal 2x per peminjaman
        max_extends = 2
        extend_count = getattr(borrowing, 'extend_count', 0)
        if extend_count >= max_extends:
            flash("Batas perpanjangan sudah tercapai (maksimal 2 kali).", "warning")
            return redirect(url_for("student_dashboard"))
        
        if request.method == "POST":
            choice = request.form.get("choice")
            
            if choice == "return":
                # Kembalikan segera
                borrowing.return_date = utcnow()
                borrowing.status = "returned"
                db.session.commit()
                flash(f"{borrowing.tool.name} berhasil dikembalikan.", "success")
                return redirect(url_for("student_dashboard"))
            
            elif choice == "extend":
                # Perpanjang waktu (tambah 1x durasi pinjaman default)
                hours = get_config().loan_duration_hours
                borrowing.deadline = borrowing.deadline + timedelta(hours=hours)
                borrowing.extend_count = extend_count + 1
                db.session.commit()
                new_deadline = borrowing.deadline.strftime('%d/%m/%Y %H:%M')
                flash(f"Peminjaman {borrowing.tool.name} diperpanjang hingga {new_deadline}.", "success")
                return redirect(url_for("student_dashboard"))
        
        # GET request - tampilkan halaman konfirmasi
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

    # ============= ADMIN ROUTES =============
    @app.route("/admin/login", methods=["GET", "POST"])
    def admin_login():
        if current_admin():
            return redirect(url_for("admin_dashboard"))
        nxt = request.args.get("next") or url_for("admin_dashboard")
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            admin = Admin.query.filter_by(username=username).first()
            if admin and admin.check_password(password):
                session.permanent = True
                session["admin_id"] = admin.id
                flash(f"Login berhasil. Halo, {admin.full_name or admin.username}.", "success")
                return redirect(request.form.get("next") or nxt)
            flash("Username atau password salah.", "error")
        return render_template("admin/admin_login.html", next_url=nxt)

    @app.route("/admin/logout")
    def admin_logout():
        session.pop("admin_id", None)
        flash("Anda sudah logout.", "info")
        return redirect(url_for("index"))

    @app.route("/admin/dashboard")
    @admin_required
    def admin_dashboard():
        active = (Borrowing.query.filter_by(status="active")
                  .order_by(Borrowing.deadline.asc()).all())
        for b in active:
            b.seconds_left = b.seconds_remaining()
            b.elapsed_str = _humanize_seconds(b.elapsed_seconds())
            b.remaining_str = _humanize_seconds(b.seconds_left)
        all_tools = Tool.query.filter_by(is_active=True).all()
        total_alat = len(all_tools)
        tersedia = sum(1 for t in all_tools if t.is_available())
        dipinjam = sum(1 for t in all_tools if not t.is_available())
        telat = sum(1 for b in active if b.is_overdue)
        recent_borrowings = (Borrowing.query.order_by(Borrowing.borrow_date.desc()).limit(20).all())

        return render_template("admin/dashboard.html", 
                               total_alat=total_alat, tersedia=tersedia, 
                               dipinjam=dipinjam, telat=telat,
                               recent_borrowings=recent_borrowings)

    @app.route("/admin/tools")
    @admin_required
    def admin_tools():
        search = request.args.get("search", "").strip()
        action = request.args.get("action", "")
        
        if action == "add":
            return render_template("admin/tool_form.html", tool=None)
        
        if action == "edit":
            code = request.args.get("code", "")
            tool = Tool.query.filter_by(code=code).first_or_404()
            return render_template("admin/tool_form.html", tool=tool)
        
        page = int(request.args.get("page", 1))
        per_page = 20
        query = Tool.query.filter_by(is_active=True)
        if search:
            query = query.filter(Tool.name.ilike(f"%{search}%") | Tool.code.ilike(f"%{search}%"))
        total = query.count()
        tools = query.order_by(Tool.code).offset((page - 1) * per_page).limit(per_page).all()
        total_pages = max(1, (total + per_page - 1) // per_page)
        return render_template("admin/tools.html", tools=tools, search=search, current_page=page, total_pages=total_pages)
    
    # Handle action-based tool CRUD via POST form
    @app.route("/admin/tools/action", methods=["POST"])
    @admin_required
    def admin_tools_action():
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
            if Tool.query.filter_by(code=code).first():
                flash(f"Kode {code} sudah dipakai.", "error")
                return redirect(url_for("admin_tools"))
            
            tool = Tool(code=code, name=name, category=category, lab_location=lab_location, 
                       condition=condition, description=description, icon=icon)
            db.session.add(tool)
            db.session.commit()
            try:
                qr_path = generate_qr_for_tool(tool)
                tool.qr_path = qr_path
                db.session.commit()
                app.logger.info(f"QR generated for {tool.code}: {qr_path}")
            except Exception as e:
                db.session.rollback()
                app.logger.error(f"QR generation failed for {tool.code}: {e}", exc_info=True)
                flash(f"Alat ditambahkan tapi QR gagal di-generate: {e}", "warning")
            flash(f"Alat {tool.name} ditambahkan.", "success")
            return redirect(url_for("admin_tools"))
        
        elif action == "update":
            old_code = request.form.get("old_code", "").strip().upper()
            tool = Tool.query.filter_by(code=old_code).first_or_404()
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
            tool = Tool.query.filter_by(code=code).first_or_404()
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
        tool = Tool.query.filter_by(code=code, is_active=True).first_or_404()
        from qr_utils import generate_qr_for_tool, qr_url_for_tool
        path = generate_qr_for_tool(tool)
        tool.qr_path = path
        db.session.commit()
        return jsonify({"success": True, "qr_code": tool.qr_url})

    @app.route("/admin/generate-all-qr")
    @admin_required
    def admin_generate_all_qr():
        tools = Tool.query.filter_by(is_active=True).all()
        for tool in tools:
            generate_qr_for_tool(tool)
        db.session.commit()
        flash(f"QR code berhasil di-generate untuk {len(tools)} alat.", "success")
        return redirect(url_for("admin_qr_labels"))

    @app.route("/admin/borrowings")
    @admin_required
    def admin_borrowings():
        search = request.args.get("search", "").strip()
        status_filter = request.args.get("status_filter", "").strip()
        q = Borrowing.query.order_by(Borrowing.borrow_date.desc())
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
                               search=search, status_filter=status_filter)

    @app.route("/admin/borrowings/export-csv")
    @admin_required
    def admin_export_borrowings_csv():
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter
        from io import BytesIO
        from flask import send_file

        search = request.args.get("search", "").strip()
        status_filter = request.args.get("status_filter", "").strip()

        q = Borrowing.query.order_by(Borrowing.borrow_date.desc())
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

        # Show gridlines
        ws.views.sheetView[0].showGridLines = True

        # Color palette & styles
        title_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
        subtitle_fill = PatternFill(start_color="334155", end_color="334155", fill_type="solid")
        header_fill = PatternFill(start_color="0F172A", end_color="0F172A", fill_type="solid")
        
        even_row_fill = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")
        odd_row_fill = PatternFill(start_color="FFFFFF", end_color="FFFFFF", fill_type="solid")

        # Status Fills & Fonts
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

        # 1. Title Banner
        ws.merge_cells("A1:K1")
        ws["A1"] = "LAPORAN REKAPITULASI PEMINJAMAN ALAT LABORATORIUM"
        ws["A1"].font = title_font
        ws["A1"].fill = title_fill
        ws["A1"].alignment = align_center
        ws.row_dimensions[1].height = 32

        # 2. Subtitle
        ws.merge_cells("A2:K2")
        now_str = utcnow().strftime("%d/%m/%Y %H:%M WIB")
        ws["A2"] = f"Sistem LabKeeper — SMK Telkom  |  Tanggal Cetak: {now_str}  |  Total Data: {len(borrowings)}"
        ws["A2"].font = subtitle_font
        ws["A2"].fill = subtitle_fill
        ws["A2"].alignment = align_center
        ws.row_dimensions[2].height = 22

        ws.row_dimensions[3].height = 10  # spacing row

        # 3. Table Headers (Row 4)
        headers = ["No", "ID", "Nama Siswa", "NIS", "Kode Alat", "Nama Alat", "Tgl Pinjam", "Batas Kembali", "Tgl Kembali", "Status", "Kondisi Akhir"]
        ws.row_dimensions[4].height = 26

        for col_idx, text in enumerate(headers, 1):
            cell = ws.cell(row=4, column=col_idx, value=text)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = align_center
            cell.border = thin_border

        # 4. Data Rows (Row 5+)
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

                # Highlight Status column
                if col_idx == 10:  # Status Column
                    if status_str == "Dikembalikan":
                        cell.fill = status_returned_fill
                        cell.font = status_returned_font
                    elif status_str == "Telat":
                        cell.fill = status_overdue_fill
                        cell.font = status_overdue_font
                    else:
                        cell.fill = status_active_fill
                        cell.font = status_active_font

        # 5. Auto-fit column widths nicely
        padding = {1: 6, 2: 8, 3: 24, 4: 14, 5: 14, 6: 24, 7: 20, 8: 20, 9: 20, 10: 16, 11: 16}
        for col_idx, width in padding.items():
            col_letter = get_column_letter(col_idx)
            ws.column_dimensions[col_letter].width = width

        # 6. Save & Stream Excel Workbook
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
        b = Borrowing.query.get_or_404(bid)
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
        """Admin force-extends a borrowing by N hours (default 2). Bypass max_extend limit."""
        b = Borrowing.query.get_or_404(bid)
        if b.status == "returned":
            flash("Peminjaman sudah dikembalikan.", "warning")
            return redirect(url_for("admin_borrowings"))
        try:
            hours = int(request.form.get("hours", 2)) if request.method == "POST" else int(request.args.get("hours", 2))
        except (TypeError, ValueError):
            hours = 2
        hours = max(1, min(hours, 168))  # 1 jam sampai 7 hari

        from datetime import timedelta
        # Kalau deadline sudah lewat, tambah dari sekarang. Kalau belum, tambah dari deadline lama.
        base = b.deadline if b.deadline > utcnow() else utcnow()
        b.deadline = base + timedelta(hours=hours)
        b.extend_count = (b.extend_count or 0) + 1
        # Auto-mark kembali ke 'active' kalau sebelumnya overdue
        if b.status == "overdue":
            b.status = "active"
        db.session.commit()
        flash(f"Deadline {b.tool_name} diperpanjang admin +{hours} jam → {b.deadline.strftime('%d/%m/%Y %H:%M')}.", "success")
        return redirect(url_for("admin_borrowings"))

    @app.route("/admin/borrowings/bulk-action", methods=["POST"])
    @admin_required
    def admin_borrowings_bulk_action():
        """Bulk operations on selected borrowings."""
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
        borrowings = Borrowing.query.filter(Borrowing.id.in_(bid_ints)).all()
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
            from datetime import timedelta
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
        search = request.args.get("search", "").strip()
        action = request.args.get("action", "")
        
        if action == "add":
            return render_template("admin/student_form.html", student=None)
        
        if action == "edit":
            nis = request.args.get("nis", "")
            student = Student.query.filter_by(nis=nis).first_or_404()
            return render_template("admin/student_form.html", student=student)
        
        query = Student.query.filter_by(is_active=True)
        if search:
            query = query.filter(
                db.or_(
                    Student.name.ilike(f"%{search}%"),
                    Student.nis.ilike(f"%{search}%"),
                    Student.class_name.ilike(f"%{search}%"),
                )
            )
        students = query.order_by(Student.class_name, Student.name).all()
        # Add active borrowing count for each student
        for s in students:
            s.active_borrowings_count = Borrowing.query.filter_by(
                student_id=s.id, status='active'
            ).count()
        return render_template("admin/students.html", students=students, search=search)

    @app.route("/admin/students/action", methods=["POST"])
    @admin_required
    def admin_students_action():
        action = request.form.get("_action", "add")
        
        if action == "add":
            nis = request.form.get("nis", "").strip()
            name = request.form.get("name", "").strip()
            class_name = request.form.get("class", "").strip()
            password = request.form.get("password", "").strip()
            
            if not nis or not name or not class_name or not password:
                flash("Semua field wajib diisi.", "error")
                return redirect(url_for("admin_students"))
            if Student.query.filter_by(nis=nis).first():
                flash("NIS sudah terdaftar.", "error")
                return redirect(url_for("admin_students"))
            s = Student(nis=nis, name=name, class_name=class_name)
            s.set_password(password)
            db.session.add(s)
            db.session.commit()
            flash(f"Siswa {s.name} ditambahkan.", "success")
            return redirect(url_for("admin_students"))
        
        elif action == "update":
            old_nis = request.form.get("old_nis", "").strip()
            s = Student.query.filter_by(nis=old_nis).first_or_404()
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
            s = Student.query.filter_by(nis=nis).first_or_404()

            # Snapshot info murid ke borrowings sebelum hapus —
            # supaya history tetap punya identitas walau student hilang.
            Borrowing.query.filter_by(student_id=s.id).update({
                Borrowing.student_id: None,
                Borrowing.archived_student_name: s.name,
                Borrowing.archived_student_nis: s.nis,
            })

            db.session.delete(s)
            db.session.commit()
            flash(
                f"Siswa {s.name} dihapus permanen. "
                f"Histori peminjaman tetap tersimpan.",
                "info",
            )
            return redirect(url_for("admin_students"))
        
        return redirect(url_for("admin_students"))

    @app.route("/admin/students/bulk-action", methods=["POST"])
    @admin_required
    def admin_students_bulk_action():
        """Bulk operations on selected students via checkbox."""
        action = request.form.get("_action", "")
        nis_list = request.form.getlist("nis")  # ambil semua NIS yang dicentang

        if not nis_list:
            flash("Pilih minimal satu siswa terlebih dahulu.", "warning")
            return redirect(url_for("admin_students"))

        students = Student.query.filter(Student.nis.in_(nis_list)).all()
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
            # Snapshot history sebelum hapus (sama seperti delete satuan)
            for s in students:
                Borrowing.query.filter_by(student_id=s.id).update({
                    Borrowing.student_id: None,
                    Borrowing.archived_student_name: s.name,
                    Borrowing.archived_student_nis: s.nis,
                })
                db.session.delete(s)
            db.session.commit()
            flash(
                f"{len(students)} siswa dihapus permanen. "
                f"Histori peminjaman tetap tersimpan.",
                "info",
            )
        else:
            flash(f"Aksi tidak dikenal: {action}", "error")

        return redirect(url_for("admin_students"))

    @app.route("/admin/qr-labels")
    @admin_required
    def admin_qr_labels():
        tools = Tool.query.filter_by(is_active=True).order_by(Tool.code).all()
        return render_template("admin/qr_labels.html", tools=tools)

    @app.route("/admin/settings", methods=["GET", "POST"])
    @admin_required
    def admin_settings():
        cfg = Config.get_solo()
        if request.method == "POST":
            cfg.loan_duration_hours = int(request.form.get("duration_hours", 24))
            db.session.commit()
            flash("Pengaturan disimpan.", "success")
            return redirect(url_for("admin_settings"))
        return render_template("admin/settings.html", settings=cfg)

    @app.route("/admin/reset-borrowings")
    @admin_required
    def admin_reset_borrowings():
        Borrowing.query.delete()
        db.session.commit()
        flash("Semua riwayat peminjaman direset.", "info")
        return redirect(url_for("admin_settings"))

    # ============= JSON API (for live countdown) =============
    @app.route("/api/active-borrowings")
    @admin_required
    def api_active_borrowings():
        active = Borrowing.query.filter_by(status="active").all()
        result = []
        for b in active:
            result.append({
                "id": b.id,
                "tool_code": b.tool.code,
                "tool_name": b.tool.name,
                "student_name": b.student.name,
                "student_nis": b.student.nis,
                "student_class": b.student.class_name,
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

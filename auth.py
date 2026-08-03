"""LabKeeper — Authentication helpers (separate sessions for student + admin)"""
from functools import wraps
from flask import session, redirect, url_for, flash, request
from models import Student, Admin


def current_student() -> Student | None:
    sid = session.get("student_id")
    if sid is None:
        return None
    s = Student.query.get(sid)
    if s is None or not s.is_active:
        return None
    # Multi-device session invalidation check
    stored_pv = session.get("student_password_version")
    if stored_pv is not None and stored_pv != (getattr(s, "password_version", 1) or 1):
        session.clear()
        return None
    return s


def current_admin() -> Admin | None:
    aid = session.get("admin_id")
    if aid is None:
        return None
    return Admin.query.get(aid)


def student_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        s = current_student()
        if s is None:
            flash("Silakan login sebagai siswa terlebih dahulu.", "warning")
            return redirect(url_for("student_login", next=request.path))
        # Paksa logout kalau akun dinonaktifkan admin
        if not s.is_active:
            session.clear()
            flash("Akun Anda sudah dinonaktifkan. Hubungi admin lab.", "error")
            return redirect(url_for("student_login"))
        return fn(*args, **kwargs)
    return wrapper


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if current_admin() is None:
            flash("Silakan login sebagai admin terlebih dahulu.", "warning")
            return redirect(url_for("admin_login", next=request.path))
        return fn(*args, **kwargs)
    return wrapper

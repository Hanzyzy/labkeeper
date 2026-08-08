import sqlite3
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def fix_db():
    conn = sqlite3.connect("instance/labkeeper.db")
    cursor = conn.cursor()
    tables = ["schools", "admins", "students", "tools", "borrowings"]

    # 1. Auto-Add Missing Columns if schema is outdated
    migrations = [
        ("schools", "loan_duration_hours", "INTEGER DEFAULT 2"),
        ("schools", "is_active", "INTEGER DEFAULT 1"),
        ("schools", "address", "TEXT"),
        ("schools", "latitude", "REAL"),
        ("schools", "longitude", "REAL"),
        ("schools", "max_geofence_radius_meters", "INTEGER DEFAULT 200"),
        ("schools", "require_geofence", "INTEGER DEFAULT 1"),
        ("admins", "full_name", "TEXT"),
        ("admins", "school_id", "INTEGER"),
        ("students", "password_version", "INTEGER DEFAULT 1"),
        ("students", "avatar_path", "TEXT"),
        ("students", "phone", "TEXT"),
        ("students", "school_id", "INTEGER"),
        ("students", "spam_count", "INTEGER DEFAULT 0"),
        ("students", "banned_until", "TEXT"),
        ("tools", "school_id", "INTEGER"),
        ("tools", "icon", "TEXT DEFAULT ''"),
        ("tools", "photo_emoji", "TEXT DEFAULT '[FIX]'"),
        ("borrowings", "school_id", "INTEGER"),
        ("borrowings", "extend_count", "INTEGER DEFAULT 0"),
        ("borrowings", "force_returned", "INTEGER DEFAULT 0"),
        ("borrowings", "archived_student_name", "TEXT"),
        ("borrowings", "archived_student_nis", "TEXT"),
        ("borrowings", "borrow_lat", "REAL"),
        ("borrowings", "borrow_lng", "REAL"),
        ("borrowings", "borrow_distance_meters", "REAL"),
        ("borrowings", "device_info", "TEXT"),
        ("borrowings", "ip_address", "TEXT"),
    ]

    for tbl, col, col_def in migrations:
        try:
            cursor.execute(f"PRAGMA table_info({tbl})")
            existing_cols = [c[1] for c in cursor.fetchall()]
            if col not in existing_cols:
                cursor.execute(f"ALTER TABLE {tbl} ADD COLUMN {col} {col_def}")
                print(f"[SUCCESS] Added missing column {tbl}.{col}")
        except Exception as e:
            print(f"Skipping migration {tbl}.{col}: {e}")

    # 2. Fix NULL default values for critical columns
    try:
        cursor.execute("UPDATE schools SET loan_duration_hours = 2 WHERE loan_duration_hours IS NULL")
        cursor.execute("UPDATE schools SET is_active = 1 WHERE is_active IS NULL")
        cursor.execute("UPDATE students SET password_version = 1 WHERE password_version IS NULL")
        cursor.execute("UPDATE students SET is_active = 1 WHERE is_active IS NULL")
        cursor.execute("UPDATE tools SET is_active = 1 WHERE is_active IS NULL")
    except Exception as e:
        print(f"Skipping null defaults fix: {e}")

    # 3. Fix Invalid Date Formats across ALL tables and columns
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    all_tables = [r[0] for r in cursor.fetchall() if not r[0].startswith('sqlite_')]
    fixed_count = 0

    for t in all_tables:
        try:
            cursor.execute(f"PRAGMA table_info('{t}')")
            cols = [c[1] for c in cursor.fetchall()]
            for col in cols:
                cursor.execute(f"SELECT rowid, [{col}] FROM [{t}] WHERE [{col}] IS NOT NULL")
                rows = cursor.fetchall()
                for r_id, val in rows:
                    if isinstance(val, str) and "/" in val:
                        val_c = val.strip()
                        t_part = "08:00:00"
                        d_part = val_c
                        if " " in val_c:
                            d_part, t_part = val_c.split(" ", 1)
                        p = d_part.split("/")
                        if len(p) == 3:
                            yyyy = p[2].split()[0]
                            mm = p[1].zfill(2)
                            dd = p[0].zfill(2)
                            n_val = f"{yyyy}-{mm}-{dd} {t_part}"
                            cursor.execute(f"UPDATE [{t}] SET [{col}] = ? WHERE rowid = ?", (n_val, r_id))
                            print(f"[SUCCESS] Fixed [{t}].[{col}] (rowid {r_id}): {val} -> {n_val}")
                            fixed_count += 1
        except Exception as e:
            print(f"Skipping {t}: {e}")

    conn.commit()
    conn.close()
    print("==========================================")
    print(f"[DONE] SUKSES: Total {fixed_count} tanggal bermasalah berhasil diperbaiki!")
    print("==========================================")

if __name__ == "__main__":
    fix_db()

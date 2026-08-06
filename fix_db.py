import sqlite3

def fix_db():
    conn = sqlite3.connect("instance/labkeeper.db")
    cursor = conn.cursor()
    tables = ["schools", "admins", "students", "tools", "borrowings"]

    fixed_count = 0
    for table in tables:
        try:
            cursor.execute(f"PRAGMA table_info({table})")
            cols = [c[1] for c in cursor.fetchall()]
            for col in cols:
                if any(k in col for k in ["created_at", "date", "deadline", "at"]):
                    cursor.execute(f"SELECT id, {col} FROM {table} WHERE {col} IS NOT NULL")
                    rows = cursor.fetchall()
                    for row_id, val in rows:
                        if isinstance(val, str) and "/" in val:
                            parts = val.split("/")
                            if len(parts) == 3:
                                new_val = f"{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)} 08:00:00"
                                cursor.execute(f"UPDATE {table} SET {col} = ? WHERE id = ?", (new_val, row_id))
                                print(f"✅ Fixed date in {table}.{col} (ID {row_id}): {val} -> {new_val}")
                                fixed_count += 1
        except Exception as e:
            print(f"Skipping {table}: {e}")

    conn.commit()
    conn.close()
    print(f"==========================================")
    print(f"✅ FINISHED! {fixed_count} date format(s) fixed.")
    print(f"==========================================")

if __name__ == "__main__":
    fix_db()

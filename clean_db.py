import sqlite3

def clean_all_dates():
    conn = sqlite3.connect('instance/labkeeper.db')
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [r[0] for r in cursor.fetchall() if not r[0].startswith('sqlite_')]
    total = 0

    for t in tables:
        cursor.execute(f"PRAGMA table_info('{t}')")
        cols = [c[1] for c in cursor.fetchall()]
        for col in cols:
            cursor.execute(f"SELECT rowid, [{col}] FROM [{t}] WHERE [{col}] IS NOT NULL")
            for r_id, val in cursor.fetchall():
                if isinstance(val, str) and '/' in val:
                    val_c = val.strip()
                    t_part = '08:00:00'
                    d_part = val_c
                    if ' ' in val_c:
                        d_part, t_part = val_c.split(' ', 1)
                    p = d_part.split('/')
                    if len(p) == 3:
                        yyyy = p[2].split()[0]
                        mm = p[1].zfill(2)
                        dd = p[0].zfill(2)
                        n_val = f"{yyyy}-{mm}-{dd} {t_part}"
                        cursor.execute(f"UPDATE [{t}] SET [{col}] = ? WHERE rowid = ?", (n_val, r_id))
                        print(f"✅ Fixed [{t}].[{col}] (rowid {r_id}): {val} -> {n_val}")
                        total += 1

    conn.commit()
    conn.close()
    print("==========================================")
    print(f"🎉 SUKSES: Total {total} tanggal bermasalah berhasil diperbaiki!")
    print("==========================================")

if __name__ == '__main__':
    clean_all_dates()

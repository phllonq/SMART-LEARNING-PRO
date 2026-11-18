import os
import sqlite3

db_path = os.path.join("database", "smart_learning.db")
print(f"DB File exists: {os.path.exists(db_path)}, Size: {os.path.getsize(db_path)} bytes")

conn = sqlite3.connect(db_path)
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
tables = [row[0] for row in cur.fetchall()]
print(f"Total tables: {len(tables)}")

for t in tables:
    cur.execute(f"SELECT COUNT(*) FROM `{t}`;")
    cnt = cur.fetchone()[0]
    cur.execute(f"PRAGMA foreign_key_list(`{t}`);")
    fks = cur.fetchall()
    fk_info = [f"{fk[3]} -> {fk[2]}.{fk[4]}" for fk in fks]
    print(f" - {t:22} | Rows: {cnt:3} | FKs: {fk_info}")

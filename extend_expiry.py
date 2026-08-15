import sqlite3
import datetime
import random
import os
import sys
import re

DB = r"C:\Users\E575\Desktop\Minimarket\SWI\inventory.db"
if not os.path.exists(DB):
    print("ERROR: DB not found", DB)
    sys.exit(1)

conn = sqlite3.connect(DB)
cur = conn.cursor()
try:
    cur.execute("SELECT id, fecha_caducidad FROM productos WHERE fecha_caducidad IS NOT NULL AND fecha_caducidad != ''")
except Exception as e:
    print("ERROR: failed to query productos:", e)
    conn.close()
    sys.exit(1)
rows = cur.fetchall()
today = datetime.date.today()
updated = []
for id_, f in rows:
    s = (f or "").strip()
    if not s:
        continue
    parsed = None
    for fmt in ("%Y-%m-%d","%Y-%m-%d %H:%M:%S","%d/%m/%Y","%d-%m-%Y"):
        try:
            piece = s[:19] if len(s) >= 19 else s
            dt = datetime.datetime.strptime(piece, fmt)
            parsed = dt.date()
            break
        except Exception:
            pass
    if not parsed:
        m = re.search(r"(\d{4}-\d{2}-\d{2})", s)
        if m:
            try:
                parsed = datetime.datetime.strptime(m.group(1), "%Y-%m-%d").date()
            except Exception:
                pass
    if not parsed:
        # could not parse
        continue
    if parsed < today:
        add = random.randint(30,60)
        new = parsed + datetime.timedelta(days=add)
        new_s = new.strftime("%Y-%m-%d")
        try:
            cur.execute("UPDATE productos SET fecha_caducidad = ? WHERE id = ?", (new_s, id_))
            updated.append((id_, s, new_s))
        except Exception as e:
            print("ERROR updating id", id_, e)

conn.commit()
print("UPDATED_COUNT:", len(updated))
for u in updated[:500]:
    print("UPDATED", u[0], u[1], "->", u[2])
if len(updated) > 500:
    print("... (more updates truncated)")
conn.close()

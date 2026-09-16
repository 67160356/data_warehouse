from pathlib import Path
import sqlite3
p=Path(__file__).resolve().parent/'data'/'oltp.db'
if not p.exists():raise SystemExit('Run lab.py first')
with sqlite3.connect(p) as con:
    print('Before:',con.execute('SELECT * FROM orders').fetchall())
    # Guarded UPDATE: match BOTH the order_id and the expected current status.
    cur = con.execute(
        "UPDATE orders SET status='PAID' WHERE order_id='O1004' AND status='PENDING'"
    )
    print('rowcount:', cur.rowcount)
    con.commit()
    print('After:',con.execute('SELECT * FROM orders').fetchall())
# Run twice. Explain why the second guarded UPDATE should affect 0 rows.

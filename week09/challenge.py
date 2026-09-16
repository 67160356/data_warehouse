"""Bonus B: copy warehouse.db -> challenge.db, add October data, re-pivot, verify."""
from pathlib import Path
import shutil, sqlite3
import pandas as pd

ROOT = Path(__file__).resolve().parent
SRC, DST = ROOT/'data'/'warehouse.db', ROOT/'data'/'challenge.db'
OUT = ROOT/'results'; OUT.mkdir(exist_ok=True)
if DST.exists(): DST.unlink()
shutil.copy2(SRC, DST)

def snapshot(con, label):
    a = con.execute('SELECT COUNT(*), COUNT(DISTINCT order_id), SUM(quantity*unit_price) FROM fact_sales').fetchone()
    b = con.execute('SELECT COUNT(*), COUNT(DISTINCT order_id), SUM(amount) FROM sales').fetchone()
    print(f'{label:7} before JOIN (fact_sales): lines={a[0]} orders={a[1]} revenue={a[2]}')
    print(f'{label:7} after  JOIN (sales view): lines={b[0]} orders={b[1]} revenue={b[2]}')
    assert a == b, 'JOIN changed the numbers -> fan-out or missing dimension row'
    return a

con = sqlite3.connect(DST)
con.execute('PRAGMA foreign_keys=ON')          # must be ON *before* INSERT
before = snapshot(con, 'BEFORE')

# New day must exist in dim_date first, otherwise the FK on fact_sales fails.
con.execute("INSERT INTO dim_date VALUES (20261001, '2026-10-01', 2026, '2026-10')")
# product_key 1=Tea(50), 2=Cookie(80) | store_key 1=Bangsaen/Chonburi, 2=Siam/Bangkok
con.executemany('INSERT INTO fact_sales VALUES (?,?,?,?,?,?,?)', [
    ('O1007', 1, 20261001, 1, 1, 3, 50),   # Tea    x3 @ Chonburi
    ('O1007', 2, 20261001, 2, 1, 2, 80),   # Cookie x2 @ Chonburi
    ('O1008', 1, 20261001, 1, 2, 4, 50),   # Tea    x4 @ Bangkok
])
assert not con.execute('PRAGMA foreign_key_check').fetchall(), 'FK violation'
con.commit()
print('\nCOMMIT ok. PRAGMA foreign_key_check -> no violations\n')

after = snapshot(con, 'AFTER')
print(f'\ndelta: +{after[0]-before[0]} lines, +{after[1]-before[1]} orders, +{after[2]-before[2]} baht')

df = pd.read_sql_query('SELECT * FROM sales', con)
con.close()
piv = df.pivot_table(index='province', columns='month', values='amount',
                     aggfunc='sum', fill_value=0, margins=True, margins_name='Total')
print('\nNew pivot (province x month) with October:\n', piv)
assert piv.loc['Total','Total'] == df['amount'].sum()
piv.to_csv(OUT/'pivot_challenge.csv', encoding='utf-8-sig')
print('\nNote: the q08 CASE WHEN pivot still shows only aug/sep - a hand-written')
print('CASE list does NOT grow by itself, while pandas columns="month" adds 2026-10 automatically.')

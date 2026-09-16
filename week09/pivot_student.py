from pathlib import Path
import sqlite3
import pandas as pd
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'results'; OUT.mkdir(exist_ok=True)
with sqlite3.connect((ROOT/'data'/'warehouse.db').as_uri()+'?mode=ro',uri=True) as con:
    df=pd.read_sql_query('SELECT * FROM sales',con)
print(df.head())

# ---------------------------------------------------------------- P1
# province x month, sum of amount, zero-filled, with row/column totals.
p1 = df.pivot_table(index='province', columns='month', values='amount',
                    aggfunc='sum', fill_value=0,
                    margins=True, margins_name='Total')
print('\n[P1] province x month (sum)\n', p1)
p1.to_csv(OUT/'pivot_province_month.csv', encoding='utf-8-sig')

# ---------------------------------------------------------------- P2
# Filter September FIRST, then pivot category x province.
sep = df[df['month'] == '2026-09']
p2 = sep.pivot_table(index='category', columns='province', values='amount',
                     aggfunc='sum', fill_value=0,
                     margins=True, margins_name='Total')
print('\n[P2] September, category x province (sum)\n', p2)
p2.to_csv(OUT/'pivot_september.csv', encoding='utf-8-sig')

# ---------------------------------------------------------------- P3
# Grand total = the single Total x Total cell, NOT the sum of every cell
# (that would count each amount three times: row total + col total + cell).
grand = p1.loc['Total', 'Total']
assert grand == df['amount'].sum(), (grand, df['amount'].sum())
print(f"\n[P3] assert OK: grand total {grand} == df['amount'].sum() {df['amount'].sum()}")
print("     naive sum of all pivot cells =", int(p1.to_numpy().sum()), "(triple counted - wrong)")

# ---------------------------------------------------------------- Mistake demo
# Without aggfunc, pivot_table defaults to MEAN.
bug = df.pivot_table(index='province', columns='month', values='amount', fill_value=0)
print('\n[BUG] no aggfunc -> mean per line, Bangkok 2026-09 =', bug.loc['Bangkok','2026-09'])
print(bug)
bug.to_csv(OUT/'pivot_bug_mean.csv', encoding='utf-8-sig')
fixed = df.pivot_table(index='province', columns='month', values='amount',
                       aggfunc='sum', fill_value=0)
print('\n[FIXED] aggfunc="sum" -> Bangkok 2026-09 =', fixed.loc['Bangkok','2026-09'])
print(fixed)
fixed.to_csv(OUT/'pivot_fixed_sum.csv', encoding='utf-8-sig')

# ---------------------------------------------------------------- Drink filter
# Excel equivalent: Filters = category, selected "Drink".
drink = df[df['category'] == 'Drink']
p_drink = drink.pivot_table(index='province', columns='month', values='amount',
                            aggfunc='sum', fill_value=0,
                            margins=True, margins_name='Total')
print('\n[DRINK] province x month, category = Drink\n', p_drink)
print('Drink grand total =', drink['amount'].sum(), 'baht')
p_drink.to_csv(OUT/'pivot_drink.csv', encoding='utf-8-sig')

# ---------------------------------------------------------------- P4 (xlsx)
with pd.ExcelWriter(OUT/'pivot.xlsx', engine='openpyxl') as xw:
    df.to_excel(xw, sheet_name='data', index=False)
    p1.to_excel(xw, sheet_name='P1_province_month')
    p2.to_excel(xw, sheet_name='P2_september')
    p_drink.to_excel(xw, sheet_name='Drink_filter')
    bug.to_excel(xw, sheet_name='BUG_mean')
print('\nSaved: pivot_province_month.csv, pivot_september.csv, pivot_drink.csv, pivot.xlsx')

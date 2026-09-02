"""
LAB: Data Integration Pipeline — TechTrove E-Commerce
=====================================================
ETL pipeline: Extract (CSV/Excel/JSON) -> Combine -> Transform -> Integrate/Validate
-> Load (Fact/Dimension) -> Analyze

รันได้ตั้งแต่ต้นจนจบ:  python pipeline.py
ไม่มีการแก้ไขไฟล์ใน data/ ทุกการแก้ไขเกิดขึ้นในโค้ดนี้เท่านั้น (reproducible + traceable)
"""

from pathlib import Path
import json
import sys
import pandas as pd

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 50)

try:                                  # รันเป็นสคริปต์
    BASE = Path(__file__).parent
except NameError:                     # รันใน Jupyter Notebook
    BASE = Path.cwd()
DATA = BASE / "data"
OUTPUT = BASE / "output"
OUTPUT.mkdir(exist_ok=True)

# ---------------------------------------------------------------- DQ log ----
DQ_LOG = []          # หลักฐานทุกแถวที่ถูกแก้ไข/คัดออก
FUNNEL = {}          # นับจำนวนแถวในแต่ละ stage


def log_dq(step, rule, action, rows, detail=""):
    """บันทึกทุกการแก้ไข/คัดออก ลง Data Quality Report"""
    DQ_LOG.append(
        {"step": step, "rule": rule, "action": action,
         "rows_affected": int(rows), "detail": str(detail)}
    )


def banner(title):
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def profile(df, name):
    """5.1 Extract & Profile — shape / columns / dtype / missing / duplicate / ตัวอย่างค่า"""
    print(f"\n--- {name} ---")
    print(f"shape      : {df.shape}")
    info = pd.DataFrame({
        "dtype": df.dtypes.astype(str),
        "missing": df.isna().sum(),
        "missing_%": (df.isna().mean() * 100).round(2),
        "n_unique": df.nunique(),
        "sample": [df[c].dropna().iloc[0] if df[c].notna().any() else None for c in df.columns],
    })
    print(info)
    print(f"duplicate rows (ทั้งแถว) : {df.duplicated().sum()}")


# ============================================================================
# 5.1 EXTRACT
# ============================================================================
banner("STEP 1 | EXTRACT & PROFILE (ข้อมูลดิบ ก่อนแก้ไขใด ๆ)")

orders_01_raw = pd.read_csv(DATA / "orders_2026_01.csv")
orders_02_raw = pd.read_csv(DATA / "orders_2026_02.csv")
customers_raw = pd.read_csv(DATA / "customers_crm.csv")
products_raw = pd.read_excel(DATA / "product_master.xlsx")

with open(DATA / "payments.json", encoding="utf-8") as f:
    payments_json = json.load(f)
# nested JSON -> flat table (payment.method / payment.status)
payments_raw = pd.json_normalize(payments_json)
payments_raw = payments_raw.rename(
    columns={"payment.method": "payment_method", "payment.status": "payment_status"}
)

for df, name in [
    (orders_01_raw, "orders_2026_01.csv"),
    (orders_02_raw, "orders_2026_02.csv"),
    (customers_raw, "customers_crm.csv"),
    (products_raw, "product_master.xlsx"),
    (payments_raw, "payments.json (normalized)"),
]:
    profile(df, name)

print("\n>> SCHEMA DRIFT ระหว่างสองเดือน")
print("   ม.ค. :", list(orders_01_raw.columns))
print("   ก.พ. :", list(orders_02_raw.columns))
print("   ต่างกัน 3 คอลัมน์ (ordered_at/qty/discount_pct), รูปแบบวันที่ (ISO vs dd/mm/yyyy),")
print("   และรูปแบบส่วนลด (float 0-1 vs string '5%')")


# ============================================================================
# 5.2 COMBINE ORDERS (schema alignment + concat)
# ============================================================================
banner("STEP 2 | SCHEMA ALIGNMENT & COMBINE ORDERS")

RENAME_FEB = {"ordered_at": "order_date", "qty": "quantity", "discount_pct": "discount"}

o1 = orders_01_raw.copy()
o1["source_file"] = "orders_2026_01.csv"
o1["order_date"] = pd.to_datetime(o1["order_date"], format="%Y-%m-%d %H:%M:%S", errors="coerce")
o1["discount"] = pd.to_numeric(o1["discount"], errors="coerce")

o2 = orders_02_raw.rename(columns=RENAME_FEB).copy()
o2["source_file"] = "orders_2026_02.csv"
# วันที่ ก.พ. เป็น dd/mm/yyyy HH:MM
o2["order_date"] = pd.to_datetime(o2["order_date"], format="%d/%m/%Y %H:%M", errors="coerce")
# ส่วนลด ก.พ. เป็นสตริง '5%' -> 0.05
o2["discount"] = (
    o2["discount"].astype("string").str.strip().str.rstrip("%").astype(float) / 100
)
log_dq("2. combine", "schema alignment (ก.พ.)", "rename + แปลง dtype",
       len(o2), "ordered_at->order_date, qty->quantity, discount_pct->discount ('5%'->0.05)")

COLS = ["order_id", "order_date", "customer_id", "product_id",
        "quantity", "unit_price", "discount", "channel", "source_file"]
orders = pd.concat([o1[COLS], o2[COLS]], ignore_index=True)

FUNNEL["1_raw_concat"] = len(orders)
print(f"orders_01 = {len(o1)} + orders_02 = {len(o2)}  ->  concat = {len(orders)} แถว")
print(f"วันที่แปลงไม่สำเร็จ (NaT): {orders['order_date'].isna().sum()} แถว")
print(orders.head())


# ============================================================================
# 5.3 TRANSFORM (clean / standardize / deduplicate)
# ============================================================================
banner("STEP 3 | CLEANING & STANDARDIZATION")

# ---- 3.1 orders: dtype + duplicate ----------------------------------------
orders["order_id"] = orders["order_id"].astype("string").str.strip()
orders["customer_id"] = orders["customer_id"].astype("string").str.strip()
orders["product_id"] = orders["product_id"].astype("string").str.strip()
orders["channel"] = orders["channel"].astype("string").str.strip()
orders["quantity"] = pd.to_numeric(orders["quantity"], errors="coerce").astype("Int64")
orders["unit_price"] = pd.to_numeric(orders["unit_price"], errors="coerce")

n_dup = orders["order_id"].duplicated().sum()
dup_ids = orders.loc[orders["order_id"].duplicated(keep=False), "order_id"].unique().tolist()
# กติกา: เก็บ order_id เดียว โดยเก็บ "ข้อมูลล่าสุดตามลำดับที่ปรากฏ" -> keep='last'
orders = orders.drop_duplicates(subset="order_id", keep="last").reset_index(drop=True)
log_dq("3. clean", "order_id ต้องไม่ซ้ำ", "drop_duplicates(keep='last')", n_dup, f"order_id: {dup_ids}")
FUNNEL["2_deduplicated"] = len(orders)
print(f"ลบ duplicate order_id : {n_dup} แถว ({dup_ids})  ->  เหลือ {len(orders)} แถว")

# ---- 3.2 customers: email / province / duplicate ---------------------------
customers = customers_raw.copy()
customers["customer_id"] = customers["customer_id"].astype("string").str.strip()
customers["full_name"] = customers["full_name"].astype("string").str.strip()

n_email_fix = (customers["email"].astype("string")
               != customers["email"].astype("string").str.strip().str.lower()).sum()
customers["email"] = customers["email"].astype("string").str.strip().str.lower()
log_dq("3. clean", "email เป็นตัวพิมพ์เล็ก/ตัดช่องว่าง", "str.strip().str.lower()", n_email_fix)

n_email_null = customers["email"].isna().sum()
log_dq("3. clean", "email ว่าง", "คงไว้เป็น NULL (ไม่ใช้เป็น key)", n_email_null)

# ชื่อจังหวัดให้เป็นมาตรฐาน (ไทย/อังกฤษ/ตัวย่อ/สะกดผิด 'ขอนเเก่น' ใช้ เ+เ)
PROVINCE_MAP = {
    "กรุงเทพมหานคร": "กรุงเทพมหานคร", "กทม.": "กรุงเทพมหานคร", "กทม": "กรุงเทพมหานคร",
    "bangkok": "กรุงเทพมหานคร",
    "ชลบุรี": "ชลบุรี", "chonburi": "ชลบุรี",
    "ระยอง": "ระยอง", "rayong": "ระยอง",
    "เชียงใหม่": "เชียงใหม่", "chiang mai": "เชียงใหม่", "chiangmai": "เชียงใหม่",
    "ภูเก็ต": "ภูเก็ต", "phuket": "ภูเก็ต",
    "ขอนแก่น": "ขอนแก่น", "khon kaen": "ขอนแก่น",
}
raw_prov = customers["province"].astype("string")
key = (raw_prov.str.strip()
       .str.replace("เเ", "แ", regex=False)      # แก้ สระ เ+เ -> แ
       .str.replace(r"\s+", " ", regex=True)
       .str.lower())
customers["province"] = key.map(PROVINCE_MAP).fillna(raw_prov.str.strip())
n_prov_fix = (raw_prov != customers["province"]).sum()
log_dq("3. clean", "ชื่อจังหวัดเป็นมาตรฐาน", "mapping ไทย/อังกฤษ/ตัวย่อ/สะกดผิด", n_prov_fix,
       f"ค่าดิบ {raw_prov.nunique()} แบบ -> {customers['province'].nunique()} จังหวัด")
print(f"จังหวัด: {raw_prov.nunique()} รูปแบบ -> {customers['province'].nunique()} ค่ามาตรฐาน "
      f"{sorted(customers['province'].unique())}")

customers["signup_date"] = pd.to_datetime(customers["signup_date"], errors="coerce")

n_cust_dup = customers["customer_id"].duplicated().sum()
cust_dup_ids = customers.loc[customers["customer_id"].duplicated(keep=False),
                             "customer_id"].unique().tolist()
customers = customers.drop_duplicates(subset="customer_id", keep="last").reset_index(drop=True)
log_dq("3. clean", "customer_id ต้องไม่ซ้ำ (dim key)", "drop_duplicates(keep='last')",
       n_cust_dup, f"customer_id: {cust_dup_ids}")
print(f"ลบ duplicate customer_id : {n_cust_dup} แถว -> เหลือ {len(customers)} ลูกค้า")

# ---- 3.3 products ----------------------------------------------------------
products = products_raw.copy()
products["product_id"] = products["product_id"].astype("string").str.strip()
products["category"] = products["category"].astype("string").str.strip()
products["active_flag"] = products["active_flag"].astype("string").str.strip().str.upper()
products["standard_price"] = pd.to_numeric(products["standard_price"], errors="coerce")
n_prod_dup = products["product_id"].duplicated().sum()
products = products.drop_duplicates(subset="product_id", keep="last").reset_index(drop=True)
log_dq("3. clean", "product_id ต้องไม่ซ้ำ (dim key)", "drop_duplicates(keep='last')", n_prod_dup)
n_inactive = (products["active_flag"] == "N").sum()
log_dq("3. clean", "สินค้า active_flag = N", "คงไว้ใน dim แต่ติดธงเพื่อการวิเคราะห์", n_inactive)

# ---- 3.4 payments ----------------------------------------------------------
payments = payments_raw.copy()
payments["order_id"] = payments["order_id"].astype("string").str.strip()
payments["payment_status"] = payments["payment_status"].astype("string").str.strip().str.upper()
payments["payment_method"] = payments["payment_method"].astype("string").str.strip()
payments["paid_at"] = pd.to_datetime(payments["paid_at"], errors="coerce")

n_pay_dup = payments["payment_id"].duplicated().sum()
payments = payments.drop_duplicates(subset="payment_id", keep="last")
log_dq("3. clean", "payment_id ต้องไม่ซ้ำ", "drop_duplicates(keep='last')", n_pay_dup)

# หากยัง 1 order มีหลาย payment event -> เก็บเหตุการณ์ล่าสุดตาม paid_at
n_multi = payments["order_id"].duplicated().sum()
payments = (payments.sort_values("paid_at")
            .drop_duplicates(subset="order_id", keep="last")
            .reset_index(drop=True))
log_dq("3. clean", "1 order = 1 payment event", "เก็บ event ล่าสุดตาม paid_at", n_multi)

n_orphan = (~payments["order_id"].isin(orders["order_id"])).sum()
orphan_ids = payments.loc[~payments["order_id"].isin(orders["order_id"]), "order_id"].tolist()
log_dq("3. clean", "orphan payment (ไม่มี order ต้นทาง)", "ไม่นำเข้า fact", n_orphan, orphan_ids)
print(f"payments: {len(payments_raw)} -> {len(payments)} แถว | orphan {n_orphan} ({orphan_ids})")
print(payments["payment_status"].value_counts().to_dict())


# ============================================================================
# 5.4 INTEGRATE & VALIDATE
# ============================================================================
banner("STEP 4 | INTEGRATION & VALIDATION")

# ---- 4.1 business rules ก่อน merge ----------------------------------------
bad_qty = orders["quantity"].isna() | (orders["quantity"] <= 0)
bad_price = orders["unit_price"].isna() | (orders["unit_price"] <= 0)
bad_disc = orders["discount"].isna() | (orders["discount"] < 0) | (orders["discount"] > 1)
bad_date = orders["order_date"].isna()

log_dq("4. validate", "quantity > 0", "คัดออกจาก fact", bad_qty.sum(),
       orders.loc[bad_qty, "order_id"].tolist())
log_dq("4. validate", "unit_price > 0 และไม่เป็นค่าว่าง", "คัดออกจาก fact", bad_price.sum(),
       orders.loc[bad_price, "order_id"].tolist())
log_dq("4. validate", "0 <= discount <= 1", "คัดออกจาก fact", bad_disc.sum(),
       orders.loc[bad_disc, "order_id"].tolist())
log_dq("4. validate", "order_date แปลงเป็น datetime ได้", "คัดออกจาก fact", bad_date.sum())

invalid = bad_qty | bad_price | bad_disc | bad_date
orders_valid = orders.loc[~invalid].copy()
FUNNEL["3_business_rule_ok"] = len(orders_valid)
print(f"business rules: คัดออก {invalid.sum()} แถว -> เหลือ {len(orders_valid)} แถว")

# ---- 4.2 merge customer (many orders : 1 customer) -------------------------
m = orders_valid.merge(
    customers[["customer_id", "full_name", "email", "province", "signup_date"]],
    on="customer_id", how="left", validate="m:1", indicator="_cust_merge")
cust_unmatched = (m["_cust_merge"] == "left_only").sum()
cust_unmatched_ids = sorted(m.loc[m["_cust_merge"] == "left_only", "customer_id"].unique().tolist())
print(f"\nmerge customer  validate='m:1' -> {m['_cust_merge'].value_counts().to_dict()}")
print(f"  unmatched customer_id: {cust_unmatched} แถว จากรหัส {cust_unmatched_ids}")
log_dq("4. integrate", "referential integrity: customer_id ต้องมีใน CRM",
       "คัดออกจาก fact", cust_unmatched, cust_unmatched_ids)

# ---- 4.3 merge product -----------------------------------------------------
m = m.merge(products[["product_id", "product_name", "category", "standard_price", "active_flag"]],
            on="product_id", how="left", validate="m:1", indicator="_prod_merge")
prod_unmatched = (m["_prod_merge"] == "left_only").sum()
prod_unmatched_ids = sorted(m.loc[m["_prod_merge"] == "left_only", "product_id"].unique().tolist())
print(f"merge product   validate='m:1' -> {m['_prod_merge'].value_counts().to_dict()}")
print(f"  unmatched product_id: {prod_unmatched} แถว จากรหัส {prod_unmatched_ids}")
log_dq("4. integrate", "referential integrity: product_id ต้องมีใน Product Master",
       "คัดออกจาก fact", prod_unmatched, prod_unmatched_ids)

# ---- 4.4 merge payment -----------------------------------------------------
m = m.merge(payments[["order_id", "payment_id", "payment_method", "payment_status", "paid_at"]],
            on="order_id", how="left", validate="1:1", indicator="_pay_merge")
pay_unmatched = (m["_pay_merge"] == "left_only").sum()
print(f"merge payment   validate='1:1' -> {m['_pay_merge'].value_counts().to_dict()}")
log_dq("4. integrate", "order ต้องมี payment event", "คัดออกจาก fact (ถือว่ายังไม่ชำระ)",
       pay_unmatched)

# ---- 4.5 filter matched + PAID --------------------------------------------
matched = m[(m["_cust_merge"] == "both") & (m["_prod_merge"] == "both")].copy()
FUNNEL["4_matched_master"] = len(matched)

not_paid = matched["payment_status"].fillna("NO_PAYMENT") != "PAID"
status_counts = matched.loc[not_paid, "payment_status"].fillna("NO_PAYMENT").value_counts().to_dict()
log_dq("4. validate", "นับยอดขายเมื่อ payment.status = PAID", "คัดออกจาก fact",
       not_paid.sum(), status_counts)
print(f"\nสถานะที่ไม่ใช่ PAID (คัดออก): {status_counts}")

fact = matched.loc[~not_paid].copy()
FUNNEL["5_paid_sales"] = len(fact)

# ---- 4.6 net_sales ---------------------------------------------------------
fact["net_sales"] = (fact["quantity"].astype(float)
                     * fact["unit_price"]
                     * (1 - fact["discount"])).round(2)


# ---- 4.7 validate_data() (Challenge) ---------------------------------------
def validate_data(df: pd.DataFrame) -> bool:
    """ตรวจ uniqueness / referential integrity / ค่านอกช่วง ของ fact table"""
    assert df["order_id"].is_unique, "FAIL: order_id ซ้ำใน fact_sales"
    assert df["customer_id"].isin(customers["customer_id"]).all(), "FAIL: customer_id ไม่มีใน dim_customer"
    assert df["product_id"].isin(products["product_id"]).all(), "FAIL: product_id ไม่มีใน dim_product"
    assert (df["quantity"] > 0).all(), "FAIL: quantity <= 0"
    assert (df["unit_price"] > 0).all(), "FAIL: unit_price <= 0"
    assert df["discount"].between(0, 1).all(), "FAIL: discount นอกช่วง 0-1"
    assert (df["payment_status"] == "PAID").all(), "FAIL: มีสถานะที่ไม่ใช่ PAID"
    assert df["net_sales"].notna().all() and (df["net_sales"] > 0).all(), "FAIL: net_sales ไม่ถูกต้อง"
    assert df["order_date"].notna().all(), "FAIL: order_date เป็น NaT"
    print("validate_data(fact_sales): PASSED ทุกข้อ")
    return True


validate_data(fact)


# ============================================================================
# 5.5 LOAD (Dimension / Fact / DQ report)
# ============================================================================
banner("STEP 5 | LOAD")

dim_customer = (customers[["customer_id", "full_name", "email", "province", "signup_date"]]
                .sort_values("customer_id").reset_index(drop=True))
dim_product = (products[["product_id", "product_name", "category", "standard_price", "active_flag"]]
               .sort_values("product_id").reset_index(drop=True))

fact_sales = fact[[
    "order_id", "order_date", "customer_id", "product_id", "province", "category",
    "channel", "payment_id", "payment_method", "payment_status",
    "quantity", "unit_price", "discount", "net_sales", "source_file",
]].sort_values("order_id").reset_index(drop=True)

dq_report = pd.DataFrame(DQ_LOG)[["step", "rule", "action", "rows_affected", "detail"]]

dim_customer.to_csv(OUTPUT / "dim_customer.csv", index=False, encoding="utf-8-sig")
dim_product.to_csv(OUTPUT / "dim_product.csv", index=False, encoding="utf-8-sig")
fact_sales.to_csv(OUTPUT / "fact_sales.csv", index=False, encoding="utf-8-sig")
dq_report.to_csv(OUTPUT / "data_quality_report.csv", index=False, encoding="utf-8-sig")

print(f"dim_customer : {dim_customer.shape}")
print(f"dim_product  : {dim_product.shape}")
print(f"fact_sales   : {fact_sales.shape}")
print("\n--- data_quality_report.csv ---")
print(dq_report.to_string(index=False, max_colwidth=45))


# ============================================================================
# 5.6 ANALYZE
# ============================================================================
banner("STEP 6 | ANALYZE")

summary_by_province = (
    fact_sales.groupby("province", as_index=False)
    .agg(orders=("order_id", "nunique"),
         customers=("customer_id", "nunique"),
         units=("quantity", "sum"),
         net_sales=("net_sales", "sum"))
    .sort_values("net_sales", ascending=False)
    .reset_index(drop=True))
summary_by_province["net_sales"] = summary_by_province["net_sales"].round(2)
summary_by_province["share_%"] = (summary_by_province["net_sales"]
                                  / summary_by_province["net_sales"].sum() * 100).round(2)

summary_by_category = (
    fact_sales.groupby("category", as_index=False)
    .agg(orders=("order_id", "nunique"),
         units=("quantity", "sum"),
         net_sales=("net_sales", "sum"),
         avg_ticket=("net_sales", "mean"))
    .sort_values("net_sales", ascending=False)
    .reset_index(drop=True))
summary_by_category[["net_sales", "avg_ticket"]] = summary_by_category[["net_sales", "avg_ticket"]].round(2)
summary_by_category["share_%"] = (summary_by_category["net_sales"]
                                  / summary_by_category["net_sales"].sum() * 100).round(2)

summary_by_province.to_csv(OUTPUT / "summary_by_province.csv", index=False, encoding="utf-8-sig")
summary_by_category.to_csv(OUTPUT / "summary_by_category.csv", index=False, encoding="utf-8-sig")

print("\n--- summary_by_province.csv ---")
print(summary_by_province.to_string(index=False))
print("\n--- summary_by_category.csv ---")
print(summary_by_category.to_string(index=False))


# ---- Data Quality funnel (Challenge) ---------------------------------------
banner("DATA QUALITY FUNNEL (ก่อน -> หลัง Integration)")
funnel_df = pd.DataFrame({"stage": list(FUNNEL.keys()), "rows": list(FUNNEL.values())})
funnel_df["dropped"] = funnel_df["rows"].diff().fillna(0).astype(int)
funnel_df["kept_%"] = (funnel_df["rows"] / funnel_df["rows"].iloc[0] * 100).round(1)
print(funnel_df.to_string(index=False))
funnel_df.to_csv(OUTPUT / "dq_funnel.csv", index=False, encoding="utf-8-sig")

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    labels = ["Raw concat", "Deduplicated", "Business rules OK", "Matched master", "PAID sales"]
    vals = funnel_df["rows"].tolist()
    fig, ax = plt.subplots(figsize=(9, 4.5))
    bars = ax.barh(labels[::-1], vals[::-1], color="#3b7dd8")
    for b, v in zip(bars, vals[::-1]):
        ax.text(v + 4, b.get_y() + b.get_height() / 2, f"{v}", va="center", fontsize=10)
    ax.set_xlim(0, max(vals) * 1.12)
    ax.set_title("TechTrove — Data Quality Funnel (raw → paid sales)")
    ax.set_xlabel("rows")
    plt.tight_layout()
    plt.savefig(OUTPUT / "dq_funnel.png", dpi=150)
    plt.close()
    print(f"บันทึกกราฟ: {OUTPUT / 'dq_funnel.png'}")
except Exception as e:  # matplotlib ไม่จำเป็นต่อการรัน pipeline
    print(f"(ข้ามการวาดกราฟ: {e})", file=sys.stderr)


# ---- คำตอบคำถามวิเคราะห์ 6 ข้อ ------------------------------------------------
banner("คำตอบคำถามวิเคราะห์")
top_prov = summary_by_province.iloc[0]
top_cat = summary_by_category.iloc[0]
print(f"1) หลัง concat = {FUNNEL['1_raw_concat']} แถว, หลังลบ duplicate order_id = {FUNNEL['2_deduplicated']} แถว")
print(f"2) customer_id ไม่พบใน CRM = {cust_unmatched} แถว ({len(cust_unmatched_ids)} รหัส) | "
      f"product_id ไม่พบใน Master = {prod_unmatched} แถว ({len(prod_unmatched_ids)} รหัส)")
print(f"3) ธุรกรรมที่ใช้ได้จริง = {len(fact_sales)} รายการ | net_sales รวม = {fact_sales['net_sales'].sum():,.2f} บาท")
print(f"4) จังหวัดยอดขายสูงสุด = {top_prov['province']} ({top_prov['net_sales']:,.2f} บาท, {top_prov['share_%']}%)")
print(f"5) หมวดสินค้ายอดขายสูงสุด = {top_cat['category']} ({top_cat['net_sales']:,.2f} บาท, {top_cat['share_%']}%)")
print("6) ดูคำอธิบายใน ANSWERS.md (merge ก่อน clean ทำให้ validate=/indicator ตรวจไม่เจอปัญหาจริง)")

print("\nเสร็จสิ้น — ไฟล์ทั้งหมดอยู่ในโฟลเดอร์ output/")

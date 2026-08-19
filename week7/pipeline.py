# -*- coding: utf-8 -*-
"""Python Data Pipeline Engineering - Lab
Incremental + Idempotent ETL for Omnichannel Retail Data Warehouse.

Source rules follow the instructor dataset/data dictionary:
- batch_1 -> batch_2 -> batch_3
- one valid order-product transaction per order_id
- invalid rows are quarantined, not silently repaired in source
- latest updated_at wins for duplicate order_id
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from datetime import datetime
import logging
import sqlite3
from typing import Iterable

import pandas as pd


@dataclass
class PipelineConfig:
    input_path: str
    output_database: str = "retail_dw.db"
    batch_list: tuple[int, ...] = (1, 2, 3)
    error_mode: str = "quarantine"  # quarantine | fail
    quarantine_path: str = "quarantine.csv"
    run_log_path: str = "pipeline_run_log.csv"


APPROVED_PROVINCES = {
    "Bangkok", "Chonburi", "Rayong", "Chanthaburi",
    "Chachoengsao", "Samut Prakan"
}
APPROVED_PAYMENT = {
    "cash": "Cash",
    "promptpay": "PromptPay",
    "bank transfer": "Bank Transfer",
    "credit card": "Credit Card",
}
APPROVED_CHANNEL = {
    "store": "Store",
    "online": "Online",
    "marketplace": "Marketplace",
    "e-commerce": "Online",
    "ecommerce": "Online",
}

LOG = logging.getLogger("retail_pipeline")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)


# ----------------------------- Extract ---------------------------------
def read_excel_source(path: str | Path, sheet: str) -> pd.DataFrame:
    return pd.read_excel(path, sheet_name=sheet, dtype=object)


def extract(config: PipelineConfig, batch: int) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    started = datetime.now()
    LOG.info("EXTRACT batch_%s start", batch)
    customers = read_excel_source(config.input_path, "customers")
    products = read_excel_source(config.input_path, "products")
    orders = read_excel_source(config.input_path, f"orders_batch_{batch}")
    orders["source_batch"] = batch
    LOG.info("EXTRACT batch_%s rows=%s started=%s ended=%s", batch, len(orders), started, datetime.now())
    return customers, products, orders


# ----------------------------- Transform --------------------------------
def normalize_payment(value):
    if pd.isna(value):
        return value
    return APPROVED_PAYMENT.get(str(value).strip().lower(), str(value).strip())


def normalize_channel(value):
    if pd.isna(value):
        return value
    return APPROVED_CHANNEL.get(str(value).strip().lower(), str(value).strip())


def transform(orders: pd.DataFrame) -> pd.DataFrame:
    df = orders.copy()
    for c in ["order_id", "customer_id", "product_id", "payment_method", "sales_channel"]:
        if c in df:
            df[c] = df[c].astype("string").str.strip()

    df["order_datetime"] = pd.to_datetime(df["order_datetime"], errors="coerce")
    df["updated_at"] = pd.to_datetime(df["updated_at"], errors="coerce")
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")
    df["unit_price"] = pd.to_numeric(df["unit_price"], errors="coerce")
    df["discount_pct"] = pd.to_numeric(df["discount_pct"], errors="coerce")
    df["payment_method"] = df["payment_method"].map(normalize_payment)
    df["sales_channel"] = df["sales_channel"].map(normalize_channel)
    return df


# ----------------------------- Validate ---------------------------------
def validate(
    orders: pd.DataFrame,
    customers: pd.DataFrame,
    products: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = orders.copy()
    customers = customers.copy()
    products = products.copy()

    customer_ids = set(customers["customer_id"].astype(str).str.strip())
    product_ids = set(products["product_id"].astype(str).str.strip())
    active_products = set(
        products.loc[products["active_flag"].astype(str).str.upper().eq("Y"), "product_id"].astype(str).str.strip()
    )

    reasons = []
    for _, r in df.iterrows():
        rs = []
        if pd.isna(r["order_id"]) or not str(r["order_id"]).strip():
            rs.append("MISSING_ORDER_ID")
        if pd.isna(r["order_datetime"]):
            rs.append("INVALID_ORDER_DATETIME")
        if pd.isna(r["updated_at"]):
            rs.append("INVALID_UPDATED_AT")
        if pd.isna(r["customer_id"]) or not str(r["customer_id"]).strip():
            rs.append("MISSING_CUSTOMER_ID")
        elif str(r["customer_id"]) not in customer_ids:
            rs.append("UNKNOWN_CUSTOMER_ID")
        if pd.isna(r["product_id"]) or not str(r["product_id"]).strip():
            rs.append("MISSING_PRODUCT_ID")
        elif str(r["product_id"]) not in product_ids:
            rs.append("UNKNOWN_PRODUCT_ID")
        elif str(r["product_id"]) not in active_products:
            rs.append("INACTIVE_PRODUCT")
        if pd.isna(r["quantity"]) or not float(r["quantity"]).is_integer() or not (1 <= int(r["quantity"]) <= 20):
            rs.append("INVALID_QUANTITY")
        if pd.isna(r["unit_price"]) or float(r["unit_price"]) <= 0:
            rs.append("INVALID_UNIT_PRICE")
        if pd.isna(r["discount_pct"]) or not (0 <= float(r["discount_pct"]) <= 100):
            rs.append("INVALID_DISCOUNT_PCT")
        if str(r["payment_method"]).strip().lower() not in APPROVED_PAYMENT:
            rs.append("INVALID_PAYMENT_METHOD")
        if str(r["sales_channel"]).strip().lower() not in {"store", "online", "marketplace"}:
            rs.append("INVALID_SALES_CHANNEL")
        reasons.append(";".join(rs))

    df["reason_code"] = reasons
    rejected = df[df["reason_code"].ne("")].copy()
    valid = df[df["reason_code"].eq("")].copy()

    if not valid.empty:
        valid["quantity"] = valid["quantity"].astype(int)
        valid["unit_price"] = valid["unit_price"].astype(float)
        valid["discount_pct"] = valid["discount_pct"].astype(float)
        valid["gross_amount"] = valid["quantity"] * valid["unit_price"]
        valid["net_amount"] = valid["gross_amount"] * (1 - valid["discount_pct"] / 100)

    return valid, rejected


def deduplicate_latest(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    if df.empty:
        return df, 0
    before = len(df)
    out = (
        df.sort_values(["order_id", "updated_at"])
        .drop_duplicates("order_id", keep="last")
        .copy()
    )
    return out, before - len(out)


# ----------------------------- SQLite -----------------------------------
SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS dim_customer (
    customer_key INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id TEXT NOT NULL UNIQUE,
    customer_name TEXT NOT NULL,
    province TEXT NOT NULL,
    segment TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS dim_product (
    product_key INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id TEXT NOT NULL UNIQUE,
    product_name TEXT NOT NULL,
    category TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS dim_date (
    date_key INTEGER PRIMARY KEY,
    full_date TEXT NOT NULL UNIQUE,
    day INTEGER NOT NULL,
    month INTEGER NOT NULL,
    quarter INTEGER NOT NULL,
    year INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS fact_sales (
    order_id TEXT PRIMARY KEY,
    date_key INTEGER NOT NULL,
    customer_key INTEGER NOT NULL,
    product_key INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price REAL NOT NULL,
    discount_pct REAL NOT NULL,
    gross_amount REAL NOT NULL,
    net_amount REAL NOT NULL,
    payment_method TEXT NOT NULL,
    sales_channel TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    source_batch INTEGER NOT NULL,
    FOREIGN KEY(date_key) REFERENCES dim_date(date_key),
    FOREIGN KEY(customer_key) REFERENCES dim_customer(customer_key),
    FOREIGN KEY(product_key) REFERENCES dim_product(product_key)
);
CREATE TABLE IF NOT EXISTS pipeline_run_log (
    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch INTEGER NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT NOT NULL,
    rows_read INTEGER NOT NULL,
    rows_valid INTEGER NOT NULL,
    rows_rejected INTEGER NOT NULL,
    rows_duplicated INTEGER NOT NULL,
    rows_loaded INTEGER NOT NULL,
    status TEXT NOT NULL,
    net_sales REAL NOT NULL DEFAULT 0
);
"""


def init_db(conn: sqlite3.Connection):
    conn.executescript(SCHEMA)


def load_dimensions(conn: sqlite3.Connection, customers: pd.DataFrame, products: pd.DataFrame):
    for _, r in customers.iterrows():
        conn.execute(
            "INSERT INTO dim_customer(customer_id,customer_name,province,segment) VALUES(?,?,?,?) "
            "ON CONFLICT(customer_id) DO UPDATE SET customer_name=excluded.customer_name, province=excluded.province, segment=excluded.segment",
            (str(r.customer_id), str(r.customer_name), str(r.province), str(r.segment)),
        )
    for _, r in products.iterrows():
        # Keep all source products in the dimension; active_flag is a source-quality rule.
        conn.execute(
            "INSERT INTO dim_product(product_id,product_name,category) VALUES(?,?,?) "
            "ON CONFLICT(product_id) DO UPDATE SET product_name=excluded.product_name, category=excluded.category",
            (str(r.product_id), str(r.product_name), str(r.category)),
        )


def get_key(conn, table: str, keycol: str, value: str, surrogate: str) -> int:
    row = conn.execute(f"SELECT {surrogate} FROM {table} WHERE {keycol}=?", (value,)).fetchone()
    if not row:
        raise KeyError(f"missing dimension {table}:{value}")
    return int(row[0])


def upsert_fact(conn: sqlite3.Connection, row) -> int:
    # Incremental rule: insert if new; update only when source updated_at is newer.
    old = conn.execute("SELECT updated_at FROM fact_sales WHERE order_id=?", (row.order_id,)).fetchone()
    if old:
        old_dt = pd.to_datetime(old[0], errors="coerce")
        if pd.notna(old_dt) and row.updated_at <= old_dt:
            return 0

    date_key = int(row.order_datetime.strftime("%Y%m%d"))
    conn.execute(
        "INSERT INTO dim_date(date_key,full_date,day,month,quarter,year) VALUES(?,?,?,?,?,?) "
        "ON CONFLICT(date_key) DO NOTHING",
        (date_key, row.order_datetime.strftime("%Y-%m-%d"), row.order_datetime.day,
         row.order_datetime.month, row.order_datetime.quarter, row.order_datetime.year),
    )
    customer_key = get_key(conn, "dim_customer", "customer_id", str(row.customer_id), "customer_key")
    product_key = get_key(conn, "dim_product", "product_id", str(row.product_id), "product_key")
    conn.execute(
        """INSERT INTO fact_sales(order_id,date_key,customer_key,product_key,quantity,unit_price,discount_pct,
           gross_amount,net_amount,payment_method,sales_channel,updated_at,source_batch)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(order_id) DO UPDATE SET
             date_key=excluded.date_key, customer_key=excluded.customer_key, product_key=excluded.product_key,
             quantity=excluded.quantity, unit_price=excluded.unit_price, discount_pct=excluded.discount_pct,
             gross_amount=excluded.gross_amount, net_amount=excluded.net_amount,
             payment_method=excluded.payment_method, sales_channel=excluded.sales_channel,
             updated_at=excluded.updated_at, source_batch=excluded.source_batch""",
        (str(row.order_id), date_key, customer_key, product_key, int(row.quantity), float(row.unit_price),
         float(row.discount_pct), float(row.gross_amount), float(row.net_amount), str(row.payment_method),
         str(row.sales_channel), row.updated_at.isoformat(), int(row.source_batch)),
    )
    return 1


def append_quarantine(path: str, rejected: pd.DataFrame):
    if rejected.empty:
        return
    out = rejected.copy()
    out["order_datetime"] = out["order_datetime"].astype("string")
    out["updated_at"] = out["updated_at"].astype("string")
    cols = ["order_id","order_datetime","customer_id","product_id","quantity","unit_price",
            "discount_pct","payment_method","sales_channel","updated_at","source_batch","reason_code"]
    for c in cols:
        if c not in out: out[c] = ""
    out[cols].to_csv(path, mode="a", header=not Path(path).exists(), index=False)


def append_run_log(path: str, row: dict):
    pd.DataFrame([row]).to_csv(path, mode="a", header=not Path(path).exists(), index=False)


def run_pipeline(config: PipelineConfig, batch: int) -> dict:
    started = datetime.now()
    try:
        customers, products, raw = extract(config, batch)
        transformed = transform(raw)
        valid, rejected = validate(transformed, customers, products)
        rows_valid_before_dedup = len(valid)
        valid, duplicated = deduplicate_latest(valid)

        db_path = Path(config.output_database)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(db_path) as conn:
            init_db(conn)
            load_dimensions(conn, customers, products)
            loaded = 0
            net_sales = 0.0
            for row in valid.itertuples(index=False):
                inserted = upsert_fact(conn, row)
                loaded += inserted
                if inserted:
                    net_sales += float(row.net_amount)
            conn.commit()

        append_quarantine(config.quarantine_path, rejected)
        status = "success"
        ended = datetime.now()
        logrow = dict(batch=batch, started_at=started.isoformat(timespec="seconds"), ended_at=ended.isoformat(timespec="seconds"),
                      rows_read=len(raw), rows_valid=rows_valid_before_dedup, rows_rejected=len(rejected), rows_duplicated=duplicated,
                      rows_loaded=loaded, status=status, net_sales=round(net_sales,2))
        append_run_log(config.run_log_path, logrow)
        LOG.info("batch_%s complete: %s", batch, logrow)
        return logrow
    except Exception as exc:
        ended = datetime.now()
        logrow = dict(batch=batch, started_at=started.isoformat(timespec="seconds"), ended_at=ended.isoformat(timespec="seconds"),
                      rows_read=0, rows_valid=0, rows_rejected=0, rows_duplicated=0, rows_loaded=0,
                      status=f"failed: {type(exc).__name__}: {exc}", net_sales=0)
        append_run_log(config.run_log_path, logrow)
        if config.error_mode == "fail":
            raise
        LOG.exception("batch_%s failed", batch)
        return logrow


def run_all(config: PipelineConfig):
    results=[]
    for batch in config.batch_list:
        results.append(run_pipeline(config,batch))
    return pd.DataFrame(results)


if __name__ == "__main__":
    cfg = PipelineConfig(
        input_path="Python_Data_Pipeline_Lab_Data.xlsx",
        output_database="retail_dw.db",
        batch_list=(1,2,3),
        error_mode="quarantine",
    )
    # Instructor requires evidence of four rounds: batch_1, batch_1 repeat, batch_2, batch_3.
    run_pipeline(cfg, 1)
    run_pipeline(cfg, 1)
    run_pipeline(cfg, 2)
    run_pipeline(cfg, 3)

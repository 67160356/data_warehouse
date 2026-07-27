# -*- coding: utf-8 -*-
"""Homework.ipynb

Dataset: Retail Store Logs (retail_logs.csv)
Star Schema: fact_sales + dim_location, dim_product, dim_time
"""

import pandas as pd
import sqlite3

#โหลดข้อมูล
df_raw = pd.read_csv('/content/retail_logs.csv')

#ตรวจสอบโครงสร้าง
df_raw.info()
df_raw.head()

#ลบ Sale_ID ที่ซ้ำกัน (เก็บแถวแรก)
df_raw = df_raw.drop_duplicates(subset=['Sale_ID'], keep='first')

#ทำความสะอาดคอลัมน์ข้อความ กันปัญหาตัวพิมพ์เล็ก/ใหญ่และช่องว่าง
#เช่น bangsaen vs Bangsaen vs BANGSAEN, BEVERAGE vs Beverage
df_raw['Store_Code'] = df_raw['Store_Code'].str.strip()
df_raw['Branch'] = df_raw['Branch'].str.strip().str.title()
df_raw['Province'] = df_raw['Province'].str.strip().str.title()
df_raw['Region'] = df_raw['Region'].str.strip().str.title()
df_raw['Product_Name'] = df_raw['Product_Name'].str.strip().str.title()
df_raw['Category'] = df_raw['Category'].str.strip().str.title()

#เติม Region ที่ว่างโดยอ้างอิงจาก Store_Code เดียวกันที่มีค่าอยู่แล้ว
region_lookup = df_raw.dropna(subset=['Region']).drop_duplicates('Store_Code').set_index('Store_Code')['Region']
df_raw['Region'] = df_raw['Region'].fillna(df_raw['Store_Code'].map(region_lookup))

#สร้าง dim_location จาก Store_Code, Branch, Province, Region ที่ไม่ซ้ำกัน
dim_location = df_raw[['Store_Code','Branch','Province','Region']].drop_duplicates(subset=['Store_Code'])
dim_location = dim_location.dropna(subset=['Store_Code'])

#สร้าง Surrogate key (location_id)
dim_location = dim_location.reset_index(drop=True)
dim_location['location_id'] = dim_location.index + 1

#จัดเรียงคอลัมน์ให้ Pk อยู่หน้าสุด
dim_location = dim_location[['location_id','Store_Code','Branch','Province','Region']]

#สร้าง dim_product จาก Product_Name + Category ที่ไม่ซ้ำกัน
dim_product = df_raw[['Product_Name','Category']].drop_duplicates(subset=['Product_Name']).reset_index(drop=True)
dim_product['product_id'] = dim_product.index + 1

#สร้าง Fact table
#นำ location_id กลับไปใส่ใน Fact table ผ่านการ join (join ด้วย Store_Code เพราะ 1 store = 1 location)
fact_sales = pd.merge(df_raw, dim_location[['location_id','Store_Code']], on='Store_Code', how='left')

#ลบคอลัมน์ text ทิ้ง เหลือไว้เพียง Foreign Key
fact_sales = fact_sales.drop(columns=['Store_Code','Branch','Province','Region'])

#join กลับเข้า fact_sales แล้วดรอปคอลัมน์ text ทิ้ง
fact_sales = pd.merge(fact_sales, dim_product[['product_id','Product_Name']], on='Product_Name', how='left')
fact_sales = fact_sales.drop(columns=['Product_Name','Category'])

#แปลง Sale_Date ที่รูปแบบไม่ตรงกันให้เป็น datetime ก่อน
df_raw['Sale_Date_clean'] = pd.to_datetime(df_raw['Sale_Date'], format='mixed', dayfirst=True)

#สร้าง dim_time จากวันที่ไม่ซ้ำกัน
dim_time = df_raw[['Sale_Date_clean']].drop_duplicates().reset_index(drop=True)
dim_time = dim_time.rename(columns={'Sale_Date_clean':'date'})
dim_time['time_id'] = dim_time.index + 1
dim_time['year']    = dim_time['date'].dt.year
dim_time['month']   = dim_time['date'].dt.month
dim_time['day']     = dim_time['date'].dt.day
dim_time['quarter'] = dim_time['date'].dt.quarter

#join กลับเข้า fact_sales
fact_sales = pd.merge(fact_sales, df_raw[['Sale_ID','Sale_Date_clean']], on='Sale_ID', how='left')
fact_sales = pd.merge(fact_sales, dim_time, left_on='Sale_Date_clean', right_on='date', how='left')
fact_sales = fact_sales.drop(columns=['Sale_Date_clean','date'])

#เติมส่วนลดที่ว่างด้วย 0 แล้วคำนวณยอดขายสุทธิ (Amount) หลังหักส่วนลด
fact_sales['Discount_Percent'] = fact_sales['Discount_Percent'].fillna(0)
fact_sales['Amount'] = (fact_sales['Quantity'] * fact_sales['Unit_Price'] * (1 - fact_sales['Discount_Percent'] / 100)).round(2)

#สร้าง connection ไปที่ file db.
conn = sqlite3.connect('warehouse.db')
cursor = conn.cursor()

#สร้าง dimension พร้อม กำหนด primary key
# 1. สร้างตาราง dim_location
cursor.execute('''
    CREATE TABLE IF NOT EXISTS dim_location (
        location_id INTEGER PRIMARY KEY,
        Store_Code TEXT,
        Branch TEXT,
        Province TEXT,
        Region TEXT
    )
''')
# 2. สร้างตาราง dim_product
cursor.execute('''
    CREATE TABLE IF NOT EXISTS dim_product (
        product_id INTEGER PRIMARY KEY,
        Product_Name TEXT,
        Category TEXT
    )
''')
# 3. สร้างตาราง dim_time
cursor.execute('''
    CREATE TABLE IF NOT EXISTS dim_time (
        time_id INTEGER PRIMARY KEY,
        date TEXT,
        year INTEGER,
        month INTEGER,
        day INTEGER,
        quarter INTEGER
    )
''')
# 4. สร้างตาราง fact_sales พร้อม Foreign Key อ้างอิงไปยัง dimension ทั้งหมด
cursor.execute('''
    CREATE TABLE IF NOT EXISTS fact_sales (
        Sale_ID TEXT PRIMARY KEY,
        location_id INTEGER,
        product_id INTEGER,
        time_id INTEGER,
        Quantity INTEGER,
        Unit_Price REAL,
        Discount_Percent REAL,
        Amount REAL,
        FOREIGN KEY (location_id) REFERENCES dim_location(location_id),
        FOREIGN KEY (product_id) REFERENCES dim_product(product_id),
        FOREIGN KEY (time_id) REFERENCES dim_time(time_id)
    )
''')
conn.commit()

#เปิดใช้งานการตรวจสอบ Foreign Key ใน SQLite
cursor.execute('PRAGMA foreign_keys = ON;')

#โหลดข้อมูล Dimension
dim_location.to_sql('dim_location', con=conn,
                     if_exists='replace', index=False)

dim_product.to_sql('dim_product', con=conn,
                    if_exists='replace', index=False)

dim_time.to_sql('dim_time', con=conn,
                 if_exists='replace', index=False)

#โหลดข้อมูล Fact
fact_sales.to_sql('fact_sales', con=conn,
                   if_exists='replace', index=False)

print('ETL Pipeline ran successfully!')

query = '''
SELECT
    l.Branch,
    l.Province,
    SUM(f.Amount) as Total_Sales
FROM fact_sales f
JOIN dim_location l ON f.location_id = l.location_id
GROUP BY l.Branch, l.Province
ORDER BY Total_Sales DESC
LIMIT 5;
'''

result = pd.read_sql_query(query, conn)
print(result)

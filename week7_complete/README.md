# Python Data Pipeline Engineering - Week 7

## 1. งานที่ทำ
โปรเจกต์นี้สร้าง ETL Pipeline สำหรับข้อมูลยอดขายแบบ **Incremental และ Idempotent** ตามโจทย์ Lab ของอาจารย์ โดยใช้ข้อมูล Omnichannel Retail Data Warehouse ช่วง January-June 2026 ซึ่งเป็นข้อมูลจำลอง และกำหนดให้โหลด `batch_1 -> batch_2 -> batch_3` ตามลำดับ ข้อมูลต้นฉบับมี Missing, Duplicate, Invalid และ Inconsistent values จึงไม่แก้ source โดยตรง

เป้าหมายปลายทางคือ Star Schema: `fact_sales + dim_customer + dim_product + dim_date` และ Grain ของ `fact_sales` คือ 1 รายการขายสินค้าที่ผ่านการตรวจสอบต่อ `order_id`.

## 2. ไฟล์ในโฟลเดอร์
- `Python_Data_Pipeline_Lab_Data.xlsx` — source workbook ที่สร้างจากข้อมูลใน PDF ที่อาจารย์ให้มา โดยคงค่าผิดปกติไว้เพื่อให้ Pipeline ตรวจสอบเอง
- `pipeline.py` — Source code ของ ETL Pipeline ตั้งแต่ Extract -> Transform -> Validate -> Load
- `notebook.ipynb` — Notebook สำหรับรันและตรวจสอบงาน
- `retail_dw.db` — SQLite Database หลังรันครบ 3 batch และทดสอบ batch_1 ซ้ำ
- `quarantine.csv` — รายการที่ไม่ผ่าน Data Quality พร้อม `reason_code` และ `source_batch`
- `pipeline_run_log.csv` — ประวัติการรัน 4 รอบ
- `data_quality_report.csv` — สรุปเหตุผลของข้อมูลที่ถูก quarantine
- `README.md` — วิธีติดตั้ง วิธีรัน โครงสร้าง Star Schema และ Reflection

## 3. วิธีติดตั้ง
```bash
pip install pandas openpyxl
```

ใช้ Python 3.10+ แนะนำ

## 4. วิธีรัน
วางไฟล์ทั้งหมดไว้ในโฟลเดอร์เดียวกัน แล้วรัน

```bash
python pipeline.py
```

Pipeline จะทำ 4 รอบตาม Acceptance/Task ของอาจารย์:
1. `batch_1`
2. `batch_1` ซ้ำ เพื่อพิสูจน์ Idempotency
3. `batch_2`
4. `batch_3`

## 5. Data Quality ที่ตรวจ
- แปลง `order_datetime` และ `updated_at` ด้วย `errors="coerce"`
- แปลง `quantity`, `unit_price`, `discount_pct` เป็นตัวเลขอย่างปลอดภัย
- `quantity` ต้องเป็นจำนวนเต็ม 1-20
- `unit_price` ต้องมากกว่า 0
- `discount_pct` ต้องอยู่ระหว่าง 0-100
- `customer_id` ต้องมีอยู่ใน `customers`
- `product_id` ต้องมีอยู่ใน `products`
- สินค้า inactive จะถูก quarantine
- Normalize `payment_method` โดยไม่สนตัวพิมพ์เล็ก/ใหญ่
- Map `E-Commerce` เป็น `Online`
- Deduplicate ด้วย `order_id` โดยเก็บ `updated_at` ล่าสุด
- สร้าง `gross_amount = quantity * unit_price`
- สร้าง `net_amount = gross_amount * (1 - discount_pct/100)`

## 6. Reason Code หลัก
- `INVALID_ORDER_DATETIME`
- `INVALID_UPDATED_AT`
- `MISSING_CUSTOMER_ID`
- `UNKNOWN_CUSTOMER_ID`
- `MISSING_PRODUCT_ID`
- `UNKNOWN_PRODUCT_ID`
- `INACTIVE_PRODUCT`
- `INVALID_QUANTITY`
- `INVALID_UNIT_PRICE`
- `INVALID_DISCOUNT_PCT`
- `INVALID_PAYMENT_METHOD`
- `INVALID_SALES_CHANNEL`

ถ้ามีหลายปัญหาในแถวเดียว จะเก็บหลาย reason code โดยคั่นด้วย `;`

## 7. Star Schema

### dim_customer
- `customer_key` PK
- `customer_id` UNIQUE
- `customer_name`
- `province`
- `segment`

### dim_product
- `product_key` PK
- `product_id` UNIQUE
- `product_name`
- `category`

### dim_date
- `date_key` PK
- `full_date` UNIQUE
- `day`
- `month`
- `quarter`
- `year`

### fact_sales
- `order_id` PK
- `date_key` FK
- `customer_key` FK
- `product_key` FK
- `quantity`
- `unit_price`
- `discount_pct`
- `gross_amount`
- `net_amount`
- `payment_method`
- `sales_channel`
- `updated_at`
- `source_batch`

`order_id` เป็น Primary Key เพื่อป้องกันข้อมูลซ้ำ และใช้ `updated_at` เพื่อรองรับ Incremental Upsert

## 8. ผลการรัน

| รอบ | Batch | Rows Read | Valid ก่อน Dedup | Rejected | Duplicated | Loaded | Status |
|---|---:|---:|---:|---:|---:|---:|---|
| 1 | 1 | 420 | 373 | 47 | 0 | 373 | success |
| 2 | 1 ซ้ำ | 420 | 373 | 47 | 0 | 0 | success |
| 3 | 2 | 469 | 407 | 62 | 1 | 406 | success |
| 4 | 3 | 379 | 329 | 50 | 1 | 325 | success |

หมายเหตุ: `rows_read = valid + rejected` ก่อน deduplicate ตาม Acceptance Test ของโจทย์

หลังรันครบ 3 batch:
- `fact_sales` = 1,103 rows
- `dim_customer` = 180 rows
- `dim_product` = 48 rows
- `dim_date` = 169 rows
- `SUM(net_amount)` = 2,697,350.29
- `order_id` ใน Fact ไม่ซ้ำ
- Foreign Key ของ Fact เชื่อม Dimension ได้ครบ

## 9. Acceptance Tests
1. Pipeline รันครบ 3 batch โดยไม่แก้ source data
2. `order_id` ใน `fact_sales` ไม่ซ้ำ
3. Foreign key ของ Fact เชื่อม Dimension ได้ทุกแถว
4. `quantity`, `unit_price`, `net_amount` ของ Fact ไม่ติดลบ
5. รัน `batch_1` ซ้ำแล้วจำนวน Fact ไม่เพิ่ม
6. ทุกแถวที่ถูก reject มี `reason_code`
7. Run log แสดง `read = valid + rejected` ก่อน dedup

## 10. Reflection
Availability สำคัญกว่า Strictness ใน Production Pipeline เพราะข้อมูลจริงอาจมีบางแถวผิดพลาด แต่ไม่ควรทำให้ข้อมูลทั้ง batch หยุดทำงานทั้งหมด
การ quarantine ทำให้แถวที่ผิดถูกแยกออกมาเพื่อแก้ไขภายหลังได้
ส่วนข้อมูลที่ถูกต้องยังสามารถโหลดเข้า Data Warehouse ได้ตามปกติ
วิธีนี้ช่วยลดผลกระทบต่อผู้ใช้และงานวิเคราะห์ที่ต้องใช้ข้อมูลต่อเนื่อง
Pipeline ยังมี run log ทำให้ตรวจสอบได้ว่าแต่ละรอบมีข้อมูลเข้าและข้อมูลเสียเท่าไร
ดังนั้น Production Pipeline ควรยืดหยุ่นกับข้อผิดพลาดรายแถว แต่ต้องรักษากฎคุณภาพของข้อมูลที่โหลดเข้าสู่ Fact

## 11. หมายเหตุสำคัญ
ไฟล์ PDF ที่แนบมาเป็นเอกสาร Dataset ที่แสดงข้อมูลเป็นหลายหน้า ไม่ใช่ไฟล์ Excel ต้นฉบับโดยตรง ดังนั้น `Python_Data_Pipeline_Lab_Data.xlsx` ในโฟลเดอร์นี้เป็น **source workbook ที่ reconstruct จาก PDF** เพื่อให้สามารถรัน Lab ได้ และตั้งใจคงข้อมูลผิดปกติที่โจทย์กำหนดไว้ ไม่ได้แก้ค่าผิดใน source ก่อนเข้า Pipeline

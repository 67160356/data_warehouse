# ส่งงานแลป OLTP / OLAP / Pivot (week09)

## ไฟล์โค้ด
- `q01.sql` – `q12.sql` : คำตอบ SQL ทีละข้อ (รันด้วย `python query.py data/warehouse.db q0X.sql`)
- `bonus_a1.sql`, `bonus_a2.sql` : โจทย์ต่อยอด ข้อ ก. (รันกับ `data/extended.db`)
- `oltp_demo.py` : ภารกิจ 1 (guarded UPDATE)
- `pivot_student.py` : P1–P4 + ตัวอย่างบั๊ก mean + Pivot กรอง Drink
- `challenge.py` : โจทย์ต่อยอด ข้อ ข. (สร้าง challenge.db แล้วตรวจก่อน–หลัง JOIN)

## ไฟล์ผลลัพธ์ (results/)
- `Lab_Report.docx` : รายงานคำตอบ พร้อมแผนภาพ Star Schema
- `star_schema.png` : แผนภาพ Star Schema
- `q01.out` – `q12.out`, `all_query_output.txt` : ผลรันแต่ละข้อ
- `oltp_run.txt` : ผลรัน oltp_demo.py สองรอบ
- `pivot_run.txt` : ผลรัน pivot_student.py ทั้งหมด (รวม assert)
- `pivot_province_month.csv` (P1), `pivot_september.csv` (P2), `pivot_drink.csv`
- `pivot_bug_mean.csv` (ก่อนแก้ ได้ 270) / `pivot_fixed_sum.csv` (หลังแก้ ได้ 540)
- `pivot.xlsx` : Pivot ทุกชุดในไฟล์ Excel
- `pivot_challenge.csv`, `challenge_run.txt`, `bonus_a.txt` : โจทย์ต่อยอด
- `foreign_key_check.txt`, `summary_stats.txt`

## ตัวเลขหลักที่ตรวจแล้ว
8 บรรทัด / 6 ออเดอร์ / 23 ชิ้น / 1,390 บาท  |  AOV = 231.67 บาท
490 + 900 = 1,390 ✔   |   360 + 300 + 240 = 900 ✔   |   ก่อน JOIN = หลัง JOIN ✔

## ก่อนส่ง อย่าลืม
1. เปลี่ยนชื่อไฟล์ ZIP เป็น `<รหัสนิสิต>_olap_lab.zip`
2. กรอกชื่อ–รหัส–กลุ่มเรียน ในหน้าแรกของ `Lab_Report.docx`
3. กรอกหัวข้อ "การใช้ AI" ในส่วนที่ 6 ตามความจริง

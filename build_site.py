import csv
import html
import os
from pathlib import Path

from grades import average, grade

OUTPUT_DIR = Path("_site")


def load_scores(csv_path):
    """อ่านไฟล์ CSV คืนค่าเป็น list ของ (ชื่อ, คะแนน)"""
    with open(csv_path, encoding="utf-8") as f:
        return [(row["name"], int(row["score"])) for row in csv.DictReader(f)]


def render_html(rows, title):
    """สร้างหน้าเว็บ HTML จากข้อมูลคะแนน"""
    table_rows = "\n".join(
        f"<tr><td>{html.escape(name)}</td><td>{score}</td><td>{grade(score)}</td></tr>"
        for name, score in rows
    )
    avg = average([score for _, score in rows])
    return f"""<!DOCTYPE html>
<html lang="th">
<head><meta charset="UTF-8"><title>{html.escape(title)}</title></head>
<body>
<h1>{html.escape(title)}</h1>
<table>
<tr><th>ชื่อ</th><th>คะแนน</th><th>เกรด</th></tr>
{table_rows}
</table>
<p>ค่าเฉลี่ย: {avg}</p>
</body>
</html>
"""


def main():
    title = os.environ.get("SITE_TITLE") or "67160356 พิชชานันท์"
    rows = load_scores("data/scores.csv")
    OUTPUT_DIR.mkdir(exist_ok=True)
    (OUTPUT_DIR / "index.html").write_text(render_html(rows, title), encoding="utf-8")
    print(f"Built {OUTPUT_DIR / 'index.html'} ({len(rows)} students)")


if __name__ == "__main__":
    main()

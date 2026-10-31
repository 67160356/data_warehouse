def grade(score):
    """แปลงคะแนน 0-100 เป็นเกรด"""
    if not 0 <= score <= 100:
        raise ValueError("คะแนนต้องอยู่ระหว่าง 0-100")
    if score >= 80:
        return "A"
    if score >= 70:
        return "B"
    if score >= 60:
        return "C"
    if score >= 50:
        return "D"
    return "F"


def average(scores):
    """หาค่าเฉลี่ย ถ้าไม่มีข้อมูลให้ error"""
    if not scores:
        raise ValueError("ต้องมีคะแนนอย่างน้อย 1 ค่า")
    return round(sum(scores) / len(scores), 2)


def pass_rate(scores):
    """เปอร์เซ็นต์คนที่ได้ 50 คะแนนขึ้นไป"""
    passed = [s for s in scores if s >= 50]
    return round(len(passed) / len(scores) * 100, 2)

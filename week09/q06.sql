-- q06: Dice = fix SEVERAL dimensions at once (month + category + province list).
SELECT province,
       category,
       SUM(amount) AS revenue
FROM sales
WHERE month = '2026-09'
  AND category = 'Drink'
  AND province IN ('Bangkok', 'Chonburi')
GROUP BY province, category
ORDER BY revenue DESC, province;

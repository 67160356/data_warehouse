-- q04: Drill-down on the time hierarchy, month -> day, September only.
SELECT full_date,
       SUM(amount) AS revenue
FROM sales
WHERE month = '2026-09'
GROUP BY full_date
ORDER BY full_date;

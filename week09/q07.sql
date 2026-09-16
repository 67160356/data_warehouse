-- q07: WHERE filters rows BEFORE grouping, HAVING filters groups AFTER SUM.
SELECT province,
       SUM(amount) AS revenue
FROM sales
WHERE month = '2026-09'
GROUP BY province
HAVING SUM(amount) > 400
ORDER BY revenue DESC, province;

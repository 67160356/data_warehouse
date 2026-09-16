-- q03: Roll-up month x province (adds the place dimension).
SELECT month,
       province,
       SUM(amount) AS revenue
FROM sales
GROUP BY month, province
ORDER BY month, province;

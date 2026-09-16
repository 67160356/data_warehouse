-- q02: Roll-up to month level.
SELECT month,
       SUM(amount) AS revenue
FROM sales
GROUP BY month
ORDER BY month;

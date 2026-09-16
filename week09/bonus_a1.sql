-- Bonus A1 (extended.db): top 3 stores by revenue.
SELECT store_name,
       province,
       SUM(amount)              AS revenue,
       COUNT(DISTINCT order_id) AS orders,
       ROUND(SUM(amount) * 1.0 / COUNT(DISTINCT order_id), 2) AS aov
FROM sales
GROUP BY store_name, province
ORDER BY revenue DESC
LIMIT 3;

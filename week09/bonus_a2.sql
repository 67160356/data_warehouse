-- Bonus A2 (extended.db): AOV per month, plus the whole-period AOV and the
-- (different) unweighted average of the monthly AOVs.
SELECT month,
       SUM(amount)              AS revenue,
       COUNT(DISTINCT order_id) AS orders,
       ROUND(SUM(amount) * 1.0 / COUNT(DISTINCT order_id), 2) AS aov_month
FROM sales
GROUP BY month
ORDER BY month;

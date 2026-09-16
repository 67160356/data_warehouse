-- q11: Same numbers before and after the JOIN => no fan-out, no dropped rows.
SELECT 'before_join (fact_sales)' AS source,
       COUNT(*)                   AS line_count,
       COUNT(DISTINCT order_id)   AS order_count,
       SUM(quantity * unit_price) AS revenue
FROM fact_sales
UNION ALL
SELECT 'after_join (sales view)',
       COUNT(*),
       COUNT(DISTINCT order_id),
       SUM(amount)
FROM sales;

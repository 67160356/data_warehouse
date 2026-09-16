-- q01: Grain check. 1 row in fact_sales = 1 product line inside 1 order.
SELECT COUNT(*)                   AS line_count,
       COUNT(DISTINCT order_id)   AS order_count,
       SUM(quantity)              AS units,
       SUM(amount)                AS revenue
FROM sales;

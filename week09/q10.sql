-- q10: AOV must divide by DISTINCT orders, not by line count.
-- *1.0 forces float division (SQLite would do integer division otherwise).
SELECT SUM(amount)                                              AS revenue,
       COUNT(DISTINCT order_id)                                 AS orders,
       ROUND(SUM(amount) * 1.0 / COUNT(DISTINCT order_id), 2)   AS aov,
       ROUND(AVG(amount), 2)                                    AS avg_line
FROM sales;

-- q09: Monthly rows plus a grand-total row via UNION ALL.
-- SQLite will not accept an expression in ORDER BY on a compound SELECT,
-- so the sort key is built inside a subquery instead.
SELECT period, revenue
FROM (
    SELECT month       AS period,
           SUM(amount) AS revenue,
           0           AS sort_key
    FROM sales
    GROUP BY month
    UNION ALL
    SELECT 'ALL',
           SUM(amount),
           1
    FROM sales
)
ORDER BY sort_key, period;

-- q05: Slice = fix ONE dimension (month = September), summarise by province.
SELECT province,
       SUM(amount) AS revenue
FROM sales
WHERE month = '2026-09'
GROUP BY province
ORDER BY revenue DESC, province;

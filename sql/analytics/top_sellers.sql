-- Ten sellers with the most qualifying merchandise value.
SELECT
    s.seller_id,
    s.seller_state,
    COUNT(DISTINCT f.order_id) AS orders,
    COUNT(*) AS items,
    SUM(f.price) AS merchandise_value
FROM fact_order_items AS f
JOIN dim_sellers AS s ON s.seller_key = f.seller_key
WHERE f.order_status = 'delivered'
GROUP BY s.seller_id, s.seller_state
ORDER BY merchandise_value DESC, s.seller_id
LIMIT 10;

-- Number of repeat customers at each purchase frequency.
WITH repeat_customers AS (
    SELECT
        c.customer_unique_id,
        COUNT(DISTINCT f.order_id) AS orders,
        SUM(f.price) AS merchandise_value
    FROM fact_order_items AS f
    JOIN dim_customers AS c ON c.customer_key = f.customer_key
    WHERE f.order_status = 'delivered'
    GROUP BY c.customer_unique_id
    HAVING COUNT(DISTINCT f.order_id) >= 2
)
SELECT
    orders AS orders_per_customer,
    COUNT(*) AS customers,
    SUM(merchandise_value) AS merchandise_value
FROM repeat_customers
GROUP BY orders
ORDER BY orders;

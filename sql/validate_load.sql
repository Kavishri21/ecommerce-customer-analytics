-- Run after selecting the project database.
SELECT
    (SELECT COUNT(*) FROM dim_customers) AS dim_customers,
    (SELECT COUNT(*) FROM dim_products) AS dim_products,
    (SELECT COUNT(*) FROM dim_sellers) AS dim_sellers,
    (SELECT COUNT(*) FROM dim_date) AS dim_date,
    COUNT(*) AS fact_order_items,
    COUNT(DISTINCT f.order_id) AS orders_with_items,
    COUNT(DISTINCT CASE WHEN f.order_status = 'delivered' THEN f.order_id END) AS qualifying_orders,
    COALESCE(SUM(CASE WHEN f.order_status = 'delivered' THEN 1 ELSE 0 END), 0) AS qualifying_items,
    COALESCE(SUM(f.price), 0) AS merchandise_total,
    COALESCE(SUM(f.freight_value), 0) AS freight_total,
    COALESCE(SUM(CASE WHEN c.customer_key IS NULL OR p.product_key IS NULL
                          OR s.seller_key IS NULL OR d.full_date IS NULL THEN 1 ELSE 0 END), 0)
        AS items_missing_a_dimension
FROM fact_order_items AS f
LEFT JOIN dim_customers AS c ON c.customer_key = f.customer_key
LEFT JOIN dim_products AS p ON p.product_key = f.product_key
LEFT JOIN dim_sellers AS s ON s.seller_key = f.seller_key
LEFT JOIN dim_date AS d ON d.full_date = f.purchase_date;

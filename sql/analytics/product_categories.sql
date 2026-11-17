-- Merchandise value and activity by product category.
SELECT
    COALESCE(p.product_category_name_english, p.product_category_name, 'Unknown category') AS category,
    p.category_translation_status,
    COUNT(DISTINCT f.product_key) AS products,
    COUNT(DISTINCT f.order_id) AS orders,
    COUNT(*) AS items,
    SUM(f.price) AS merchandise_value
FROM fact_order_items AS f
JOIN dim_products AS p ON p.product_key = f.product_key
WHERE f.order_status = 'delivered'
GROUP BY p.product_category_name, p.product_category_name_english, p.category_translation_status
ORDER BY merchandise_value DESC, category;

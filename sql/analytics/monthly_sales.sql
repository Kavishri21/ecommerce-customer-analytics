-- Monthly qualifying orders, merchandise value, and freight.
WITH calendar_months AS (
    SELECT DISTINCT calendar_year, calendar_month
    FROM dim_date
),
monthly_sales AS (
    SELECT
        d.calendar_year,
        d.calendar_month,
        COUNT(DISTINCT f.order_id) AS orders,
        SUM(f.price) AS merchandise_value,
        SUM(f.freight_value) AS freight_value
    FROM fact_order_items AS f
    JOIN dim_date AS d ON d.full_date = f.purchase_date
    WHERE f.order_status = 'delivered'
    GROUP BY d.calendar_year, d.calendar_month
)
SELECT
    CONCAT(m.calendar_year, '-', LPAD(m.calendar_month, 2, '0')) AS purchase_month,
    COALESCE(s.orders, 0) AS orders,
    COALESCE(s.merchandise_value, 0.00) AS merchandise_value,
    COALESCE(s.freight_value, 0.00) AS freight_value,
    LAG(COALESCE(s.merchandise_value, 0.00)) OVER (
        ORDER BY m.calendar_year, m.calendar_month
    ) AS previous_month_merchandise_value
FROM calendar_months AS m
LEFT JOIN monthly_sales AS s
    ON s.calendar_year = m.calendar_year AND s.calendar_month = m.calendar_month
ORDER BY m.calendar_year, m.calendar_month;

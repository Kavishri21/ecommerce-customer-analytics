-- MySQL 8 star schema. Run after selecting the project database.

CREATE TABLE IF NOT EXISTS dim_customers (
    customer_key INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    customer_id CHAR(32) NOT NULL UNIQUE,
    customer_unique_id CHAR(32) NOT NULL,
    customer_zip_code_prefix CHAR(5),
    customer_city VARCHAR(100),
    customer_state CHAR(2)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS dim_products (
    product_key INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    product_id CHAR(32) NOT NULL UNIQUE,
    product_category_name VARCHAR(100),
    product_category_name_english VARCHAR(100),
    category_translation_status VARCHAR(20) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS dim_sellers (
    seller_key INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    seller_id CHAR(32) NOT NULL UNIQUE,
    seller_zip_code_prefix CHAR(5),
    seller_city VARCHAR(100),
    seller_state CHAR(2)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS dim_date (
    full_date DATE PRIMARY KEY,
    calendar_year SMALLINT UNSIGNED NOT NULL,
    calendar_month TINYINT UNSIGNED NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS fact_order_items (
    order_id CHAR(32) NOT NULL,
    order_item_id SMALLINT UNSIGNED NOT NULL,
    customer_key INT UNSIGNED NOT NULL,
    product_key INT UNSIGNED NOT NULL,
    seller_key INT UNSIGNED NOT NULL,
    purchase_date DATE NOT NULL,
    order_status VARCHAR(16) NOT NULL,
    price DECIMAL(10, 2) NOT NULL,
    freight_value DECIMAL(10, 2) NOT NULL,
    PRIMARY KEY (order_id, order_item_id),
    FOREIGN KEY (customer_key) REFERENCES dim_customers (customer_key),
    FOREIGN KEY (product_key) REFERENCES dim_products (product_key),
    FOREIGN KEY (seller_key) REFERENCES dim_sellers (seller_key),
    FOREIGN KEY (purchase_date) REFERENCES dim_date (full_date),
    CHECK (order_item_id > 0),
    CHECK (price >= 0),
    CHECK (freight_value >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

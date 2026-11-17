# Olist dataset exploration

The report covers the six CSVs in `data/raw/`. It uses Pandas' default CSV type and missing-value detection. Timestamps appear as text, and numeric-looking ZIP prefixes may display without leading zeroes. Duplicate counts include each identical row after its first occurrence.

## How the files relate

- **Customers and orders.** Join on `customer_id` to find the customer record for an order. Use `customer_unique_id` to recognize the same customer across orders. The customer file contains 99,441 distinct `customer_id` values and 96,096 distinct `customer_unique_id` values, with 2,997 customer identities linked to multiple `customer_id` values. The customer identity is missing on 0 rows.
- **Orders and order items.** Orders describe the purchase as a whole. Order items describe individual entries within a purchase. Joining on `order_id` produces one result row per matching item, so order fields repeat for orders with several items. `order_item_id` is scoped to its order and is checked together with `order_id`. 775 order rows have no matching item rows. Their recorded statuses were unavailable (603), canceled (164), created (5), invoiced (2), shipped (1).
- **Products, sellers, and order items.** Each item supplies a `product_id` for product details and a `seller_id` for seller details. The same product or seller can appear on many item rows.
- **Products and category translations.** Use `product_category_name` to attach an English category label where a translation exists. A blank product category and a named category without a translation are different cases.

## Candidate primary keys

A primary key identifies a row. A candidate passes this check when all of its fields are present on every row and each value or combination occurs once. A repeat is counted after the first occurrence of a complete key.

| Dataset | Candidate key | Rows missing a key field | Repeat complete keys | Result |
| --- | --- | --- | --- | --- |
| customers | customer_id | 0 | 0 | Unique and present |
| orders | order_id | 0 | 0 | Unique and present |
| order_items | order_id, order_item_id | 0 | 0 | Unique and present |
| products | product_id | 0 | 0 | Unique and present |
| sellers | seller_id | 0 | 0 | Unique and present |
| category_translations | product_category_name | 0 | 0 | Unique and present |

## Candidate foreign keys

A foreign key links a row to a lookup record. Missing references are blank according to Pandas. Unmatched nonblank references are rows with a value absent from the lookup. The final two columns count distinct lookup IDs and show how many are unused or reused.

| Referencing column | Lookup column | Missing references | Unmatched nonblank references | Lookup IDs with no rows | Lookup IDs with multiple rows |
| --- | --- | --- | --- | --- | --- |
| orders.customer_id | customers.customer_id | 0 | 0 | 0 | 0 |
| order_items.order_id | orders.order_id | 0 | 0 | 775 | 9,803 |
| order_items.product_id | products.product_id | 0 | 0 | 0 | 14,834 |
| order_items.seller_id | sellers.seller_id | 0 | 0 | 0 | 2,586 |
| products.product_category_name | category_translations.product_category_name | 610 | 13 | 0 | 70 |

## Interpreting missing values

A blank approval or delivery timestamp may reflect an order that never reached that stage or a timestamp that was never recorded. A blank product category leaves the English category unknown. These gaps should be interpreted using the surrounding fields and the intended analysis.

## File profiles

### `olist_customers_dataset.csv`

One customer record with a location and two customer identifiers.

**Rows:** 99,441 · **Columns:** 5 · **Duplicate rows:** 0

| Column | Pandas dtype | Missing values |
| --- | --- | --- |
| customer_id | str | 0 |
| customer_unique_id | str | 0 |
| customer_zip_code_prefix | int64 | 0 |
| customer_city | str | 0 |
| customer_state | str | 0 |

**First three records in CSV order**

| Column | Record 1 | Record 2 | Record 3 |
| --- | --- | --- | --- |
| customer_id | 06b8999e2fba1a1fbc88172c00ba8bc7 | 18955e83d337fd6b2def6b18a428ac77 | 4e7b3e00288586ebd08712fdd0374a03 |
| customer_unique_id | 861eff4711a542e4b93843c6dd7febb0 | 290c77bc529b7ac935b93aa66c333dc3 | 060e732b5b29e8181a18229c7b0b2b5e |
| customer_zip_code_prefix | 14409 | 9790 | 1151 |
| customer_city | franca | sao bernardo do campo | sao paulo |
| customer_state | SP | SP | SP |

### `olist_orders_dataset.csv`

One order with its customer ID, status, and timestamps.

**Rows:** 99,441 · **Columns:** 8 · **Duplicate rows:** 0

| Column | Pandas dtype | Missing values |
| --- | --- | --- |
| order_id | str | 0 |
| customer_id | str | 0 |
| order_status | str | 0 |
| order_purchase_timestamp | str | 0 |
| order_approved_at | str | 160 |
| order_delivered_carrier_date | str | 1,783 |
| order_delivered_customer_date | str | 2,965 |
| order_estimated_delivery_date | str | 0 |

**First three records in CSV order**

| Column | Record 1 | Record 2 | Record 3 |
| --- | --- | --- | --- |
| order_id | e481f51cbdc54678b7cc49136f2d6af7 | 53cdb2fc8bc7dce0b6741e2150273451 | 47770eb9100c2d0c44946d9cf07ec65d |
| customer_id | 9ef432eb6251297304e76186b10a928d | b0830fb4747a6c6d20dea0b8c802d7ef | 41ce2a54c0b03bf3443c3d931a367089 |
| order_status | delivered | delivered | delivered |
| order_purchase_timestamp | 2017-10-02 10:56:33 | 2018-07-24 20:41:37 | 2018-08-08 08:38:49 |
| order_approved_at | 2017-10-02 11:07:15 | 2018-07-26 03:24:27 | 2018-08-08 08:55:23 |
| order_delivered_carrier_date | 2017-10-04 19:55:00 | 2018-07-26 14:31:00 | 2018-08-08 13:50:00 |
| order_delivered_customer_date | 2017-10-10 21:25:13 | 2018-08-07 15:27:45 | 2018-08-17 18:06:29 |
| order_estimated_delivery_date | 2017-10-18 00:00:00 | 2018-08-13 00:00:00 | 2018-09-04 00:00:00 |

### `olist_order_items_dataset.csv`

One item within an order, with its product, seller, price, and freight.

**Rows:** 112,650 · **Columns:** 7 · **Duplicate rows:** 0

| Column | Pandas dtype | Missing values |
| --- | --- | --- |
| order_id | str | 0 |
| order_item_id | int64 | 0 |
| product_id | str | 0 |
| seller_id | str | 0 |
| shipping_limit_date | str | 0 |
| price | float64 | 0 |
| freight_value | float64 | 0 |

**First three records in CSV order**

| Column | Record 1 | Record 2 | Record 3 |
| --- | --- | --- | --- |
| order_id | 00010242fe8c5a6d1ba2dd792cb16214 | 00018f77f2f0320c557190d7a144bdd3 | 000229ec398224ef6ca0657da4fc703e |
| order_item_id | 1 | 1 | 1 |
| product_id | 4244733e06e7ecb4970a6e2683c13e61 | e5f2d52b802189ee658865ca93d83a8f | c777355d18b72b67abbeef9df44fd0fd |
| seller_id | 48436dade18ac8b2bce089ec2a041202 | dd7ddc04e1b6c2c614352b383efe2d36 | 5b51032eddd242adc84c38acab88f23d |
| shipping_limit_date | 2017-09-19 09:45:35 | 2017-05-03 11:05:13 | 2018-01-18 14:48:30 |
| price | 58.9 | 239.9 | 199.0 |
| freight_value | 13.29 | 19.93 | 17.87 |

### `olist_products_dataset.csv`

One product with its category and descriptive fields such as dimensions.

**Rows:** 32,951 · **Columns:** 9 · **Duplicate rows:** 0

| Column | Pandas dtype | Missing values |
| --- | --- | --- |
| product_id | str | 0 |
| product_category_name | str | 610 |
| product_name_lenght | float64 | 610 |
| product_description_lenght | float64 | 610 |
| product_photos_qty | float64 | 610 |
| product_weight_g | float64 | 2 |
| product_length_cm | float64 | 2 |
| product_height_cm | float64 | 2 |
| product_width_cm | float64 | 2 |

**First three records in CSV order**

| Column | Record 1 | Record 2 | Record 3 |
| --- | --- | --- | --- |
| product_id | 1e9e8ef04dbcff4541ed26657ea517e5 | 3aa071139cb16b67ca9e5dea641aaa2f | 96bd76ec8810374ed1b65e291975717f |
| product_category_name | perfumaria | artes | esporte_lazer |
| product_name_lenght | 40.0 | 44.0 | 46.0 |
| product_description_lenght | 287.0 | 276.0 | 250.0 |
| product_photos_qty | 1.0 | 1.0 | 1.0 |
| product_weight_g | 225.0 | 1000.0 | 154.0 |
| product_length_cm | 16.0 | 30.0 | 18.0 |
| product_height_cm | 10.0 | 18.0 | 9.0 |
| product_width_cm | 14.0 | 20.0 | 15.0 |

### `olist_sellers_dataset.csv`

One seller with its location.

**Rows:** 3,095 · **Columns:** 4 · **Duplicate rows:** 0

| Column | Pandas dtype | Missing values |
| --- | --- | --- |
| seller_id | str | 0 |
| seller_zip_code_prefix | int64 | 0 |
| seller_city | str | 0 |
| seller_state | str | 0 |

**First three records in CSV order**

| Column | Record 1 | Record 2 | Record 3 |
| --- | --- | --- | --- |
| seller_id | 3442f8959a84dea7ee197c632cb2df15 | d1b65fc7debc3361ea86b5f14c68d2e2 | ce3ad9de960102d0677a81f5d0bb7b2d |
| seller_zip_code_prefix | 13023 | 13844 | 20031 |
| seller_city | campinas | mogi guacu | rio de janeiro |
| seller_state | SP | SP | RJ |

### `product_category_name_translation.csv`

One Portuguese product category paired with its English label.

**Rows:** 71 · **Columns:** 2 · **Duplicate rows:** 0

| Column | Pandas dtype | Missing values |
| --- | --- | --- |
| product_category_name | str | 0 |
| product_category_name_english | str | 0 |

**First three records in CSV order**

| Column | Record 1 | Record 2 | Record 3 |
| --- | --- | --- | --- |
| product_category_name | beleza_saude | informatica_acessorios | automotivo |
| product_category_name_english | health_beauty | computers_accessories | auto |

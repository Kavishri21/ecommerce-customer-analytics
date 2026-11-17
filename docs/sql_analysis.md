# Olist analytical SQL

The four queries use delivered order items, which meet the project's definition of a qualifying purchase. They count distinct order IDs because one order can contain several items. Merchandise value is the sum of item prices. Freight is reported separately.

## Monthly sales

A common table expression (CTE) is a named result used within a query. Here, one CTE lists the calendar months and another totals qualifying sales. A left join keeps months with zero qualifying orders. `LAG` is a window function that gives each row the merchandise value of the previous calendar month. [monthly_sales.sql](../sql/analytics/monthly_sales.sql)

Across **96,478 qualifying orders**, merchandise value totaled **13,221,498.11** and freight totaled **2,198,275.64**. November 2017 had the highest monthly merchandise value at **987,765.37** across **7,289 orders**.

The source purchase dates span September 4, 2016 through October 17, 2018. The first and last calendar months cover only part of the month. Zeroes show months with no qualifying orders in these files.

| Month | Orders | Merchandise value | Freight | Previous month merchandise |
| --- | --- | --- | --- | --- |
| 2016-09 | 1 | 134.97 | 8.49 | — |
| 2016-10 | 265 | 40,325.11 | 6,165.55 | 134.97 |
| 2016-11 | 0 | 0.00 | 0.00 | 40,325.11 |
| 2016-12 | 1 | 10.90 | 8.72 | 0.00 |
| 2017-01 | 750 | 111,798.36 | 15,684.01 | 10.90 |
| 2017-02 | 1,653 | 234,223.40 | 37,015.92 | 111,798.36 |
| 2017-03 | 2,546 | 359,198.85 | 55,132.10 | 234,223.40 |
| 2017-04 | 2,303 | 340,669.68 | 50,142.72 | 359,198.85 |
| 2017-05 | 3,546 | 489,338.25 | 77,513.15 | 340,669.68 |
| 2017-06 | 3,135 | 421,923.37 | 68,127.00 | 489,338.25 |
| 2017-07 | 3,872 | 481,604.52 | 84,694.56 | 421,923.37 |
| 2017-08 | 4,193 | 554,699.70 | 91,132.66 | 481,604.52 |
| 2017-09 | 4,150 | 607,399.67 | 93,677.82 | 554,699.70 |
| 2017-10 | 4,478 | 648,247.65 | 102,869.36 | 607,399.67 |
| 2017-11 | 7,289 | 987,765.37 | 165,598.83 | 648,247.65 |
| 2017-12 | 5,513 | 726,033.19 | 117,045.10 | 987,765.37 |
| 2018-01 | 7,069 | 924,645.00 | 153,242.46 | 726,033.19 |
| 2018-02 | 6,555 | 826,437.13 | 139,731.28 | 924,645.00 |
| 2018-03 | 7,003 | 953,356.25 | 167,241.99 | 826,437.13 |
| 2018-04 | 6,798 | 973,534.09 | 159,344.84 | 953,356.25 |
| 2018-05 | 6,749 | 977,544.69 | 151,229.83 | 973,534.09 |
| 2018-06 | 6,099 | 856,077.86 | 155,900.43 | 977,544.69 |
| 2018-07 | 6,159 | 867,953.46 | 159,853.82 | 856,077.86 |
| 2018-08 | 6,351 | 838,576.64 | 146,915.00 | 867,953.46 |
| 2018-09 | 0 | 0.00 | 0.00 | 838,576.64 |
| 2018-10 | 0 | 0.00 | 0.00 | 0.00 |

## Repeat customers

The query groups by `customer_unique_id` to track the same customer across orders. `WHERE` keeps qualifying items before grouping, and `HAVING` keeps customers with at least two distinct orders after grouping. [repeat_customers.sql](../sql/analytics/repeat_customers.sql)

**2,801 of 93,358 customers (3.00%)** made at least two qualifying purchases. Customers who first purchased near the end of the dataset had less observed time to return. Monthly cohort retention will measure return purchases relative to each customer's first purchase month.

| Orders per customer | Customers | Merchandise value |
| --- | --- | --- |
| 2 | 2,573 | 631,274.90 |
| 3 | 181 | 65,974.42 |
| 4 | 28 | 18,946.73 |
| 5 | 9 | 5,616.54 |
| 6 | 5 | 2,600.66 |
| 7 | 3 | 2,280.02 |
| 9 | 1 | 1,000.85 |
| 15 | 1 | 714.63 |

## Product categories

The query joins items to the product dimension and ranks the 74 category groups by merchandise value. It uses the English label when available, the Portuguese label when a translation is missing, and “Unknown category” when the category is blank. [product_categories.sql](../sql/analytics/product_categories.sql)

These five categories had the highest merchandise value. `Products` counts distinct products sold in qualifying orders.

| Category | Products | Orders | Items | Merchandise value |
| --- | --- | --- | --- | --- |
| health_beauty | 2,397 | 8,647 | 9,465 | 1,233,131.72 |
| watches_gifts | 1,300 | 5,495 | 5,859 | 1,166,176.98 |
| bed_bath_table | 2,991 | 9,272 | 10,953 | 1,023,434.76 |
| sports_leisure | 2,822 | 7,530 | 8,431 | 954,852.55 |
| computers_accessories | 1,600 | 6,530 | 7,644 | 888,724.61 |

The unknown category group contains **1,537 items** with **170,726.63** in merchandise value. Two named categories without English translations account for another **22 items**. An order can contain items in several categories, so adding the category order counts can count the same order more than once.

## Top sellers

The query joins items to the seller dimension and returns the ten sellers with the highest qualifying merchandise value. An order can involve several sellers. The order count is distinct within each seller. [top_sellers.sql](../sql/analytics/top_sellers.sql)

**2,970 sellers** had qualifying items. The highest-value seller recorded **226,987.93** across **1,124 orders**. The third-ranked seller had more orders than the first-ranked seller, illustrating the difference between ranking by sales value and ranking by order count.

| Seller ID | State | Orders | Items | Merchandise value |
| --- | --- | --- | --- | --- |
| `4869f7a5dfa277a7dca6462dcf3b52b2` | SP | 1,124 | 1,148 | 226,987.93 |
| `53243585a1d6dc2643021fd1853d8905` | BA | 348 | 400 | 217,940.44 |
| `4a3ca9315b744ce9f8e9374361493884` | SP | 1,772 | 1,949 | 196,882.12 |
| `fa1c13f2614d7b5c4749cbc52fecda94` | SP | 578 | 579 | 190,917.14 |
| `7c67e1448b00f6e969d365cea6b010ab` | SP | 973 | 1,355 | 186,570.05 |
| `7e93a43ef30c4f03f38b393420bc753a` | SP | 319 | 322 | 165,981.49 |
| `da8622b14eb17ae2831f4ac5b9dab84a` | SP | 1,311 | 1,548 | 159,816.87 |
| `7a67c85e85bb2ce8582c35f2203ad736` | SP | 1,145 | 1,155 | 139,658.69 |
| `1025f0e2d44d7041d6cf58b6550e0bfa` | SP | 910 | 1,420 | 138,208.56 |
| `955fee9216a65b617aa5c0531780ce60` | SP | 1,261 | 1,472 | 131,836.71 |

## Run and verify

Select the warehouse database configured by `DB_NAME` and run each SQL file independently. All four queries ran in a read-only transaction on MySQL 8.0.42. An independent calculation using the cleaned CSVs matched every returned row, including the previous-month values, customer frequencies, category totals, and seller ranking.

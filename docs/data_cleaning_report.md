# Olist data cleaning and validation

Milestone 2 applies the rules below to the six raw CSVs and saves six UTF-8 CSVs under `data/processed/`. The input findings are recorded in the [data quality assessment](data_quality_assessment.md).

## Row counts

| Processed file | Input rows | Output rows | Cells trimmed |
| --- | --- | --- | --- |
| olist_customers_dataset.csv | 99,441 | 99,441 | 0 |
| olist_orders_dataset.csv | 99,441 | 99,441 | 0 |
| olist_order_items_dataset.csv | 112,650 | 112,650 | 0 |
| olist_products_dataset.csv | 32,951 | 32,951 | 0 |
| olist_sellers_dataset.csv | 3,095 | 3,095 | 0 |
| product_category_name_translation.csv | 71 | 71 | 0 |

All six output row counts match their inputs. The whitespace count measures cells whose outer spaces were removed during import.

## Cleaning rules

- **Identifiers and ZIP prefixes.** Read source columns as text first. Validate Olist IDs as 32 lowercase hexadecimal characters. Store ZIP prefixes as five-character text, including leading zeroes. CSV stores characters, so readers should request a string dtype for these fields.
- **Dates.** Write timestamps in `YYYY-MM-DD HH:MM:SS` format using the source clock. Purchase time is required. Missing optional dates stay blank. Chronology conflicts and unusual shipping deadlines keep their source values and get review flags.
- **Numbers.** Store item positions as positive integers and product measurements and counts as nullable, nonnegative integers. Write price and freight as exact nonnegative decimal text with two decimal places. Zero amounts are allowed.
- **Categories.** Keep the Portuguese category and add its English label where available. Use `category_translation_status` to distinguish `translated`, `missing_category`, and `translation_missing`. An unavailable English label stays blank.
- **Orders.** A qualifying purchase is an order marked `delivered` with at least one item row. This is the project's purchase definition for customer analysis. The six files supply order status and item details. Every order stays available for lifecycle analysis.

## Review flags and eligibility

| Measure | Rows |
| --- | --- |
| Qualifying purchases | 96,478 |
| Orders without items | 775 |
| Orders with a chronology conflict | 1,382 |
| Orders with a fulfillment status gap | 29 |
| Item rows with a shipping deadline flagged for review | 131 |
| Products with a blank category | 610 |
| Products with a named category and no English label | 13 |
| Item rows with zero freight | 383 |

- **`has_order_items`** shows whether an order has a matching item. **`is_qualifying_purchase`** applies the delivered-with-items rule.
- **`has_chronology_conflict`** marks an order if approval, carrier handoff, or customer delivery contradicts the expected event sequence, or estimated delivery falls before the purchase day. A comparison requires both timestamps.
- **`has_fulfillment_status_gap`** marks a delivered order missing approval, handoff, or delivery time, or a canceled order with a delivery time.
- **`shipping_limit_needs_review`** marks an item when its deadline predates purchase or approval, or falls more than 365 days after purchase. The one-year threshold flags outliers for review. These flags can overlap and eligibility uses the order status and item match.

## Validation before writing

All six candidate keys passed completeness and uniqueness checks. All four required relationships passed: order to customer, and item to order, product, and seller. Category translation is an optional lookup.

A missing or duplicate key, invalid populated date or numeric value, missing purchase timestamp or amount, unknown status, or broken required reference stops the run before publishing. The error identifies the affected check and row count. A break in date chronology instead produces a review flag because the correct event time cannot be recovered from these CSVs.

## Run the pipeline

From the project root in PowerShell, run

```powershell
.\.venv\Scripts\python.exe -B -m src.processing.clean_dataset
```

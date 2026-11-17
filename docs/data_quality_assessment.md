# Olist data quality assessment

Milestone 1 covers the six local CSVs described in the [dataset exploration report](dataset_exploration.md). The checks read the source files and write this report. Dates and amounts are parsed in memory for validation.

## Customer identifiers

- Customer rows: 99,441. Distinct `customer_id` values: 99,441. Distinct `customer_unique_id` values: 96,096.
- Missing `customer_unique_id`: 0. Customer IDs pointing to multiple identities: 0. Customer IDs used by multiple orders: 0.
- Customer identities mapped to more than one `customer_id`: 2,997. Largest number of customer IDs per identity: 17.

Use `customer_id` to connect an order to its customer record. Use `customer_unique_id` to count customers across orders. Repeated values of `customer_unique_id` are consistent with the dataset's identity model.

## Order statuses and orders without items

| Order status | Orders | Share | Without items | Missing approval | Missing handoff | Missing delivery |
| --- | --- | --- | --- | --- | --- | --- |
| delivered | 96,478 | 97.02% | 0 | 14 | 2 | 8 |
| shipped | 1,107 | 1.11% | 1 | 0 | 0 | 1,107 |
| canceled | 625 | 0.63% | 164 | 141 | 550 | 619 |
| unavailable | 609 | 0.61% | 603 | 0 | 609 | 609 |
| invoiced | 314 | 0.32% | 2 | 0 | 314 | 314 |
| processing | 301 | 0.30% | 0 | 0 | 301 | 301 |
| created | 5 | 0.01% | 5 | 5 | 5 | 5 |
| approved | 2 | 0.00% | 0 | 0 | 2 | 2 |

**775 orders have no item rows**, including 0 marked delivered. An order can be recorded before its items become available, and cancellation or unavailability can interrupt fulfillment. The statuses provide context for the gaps. The source does not establish each cause.

**6 canceled orders have a customer delivery timestamp.** Delivered orders with missing timestamps and canceled orders with recorded delivery need review before using those fields as proof of a fulfillment event.

## Timestamps

Timestamp strings were parsed in memory using `YYYY-MM-DD HH:MM:SS`. The CSVs supply no time-zone offset, so the comparisons use the recorded clock values. A parse failure is a populated value that could not be read as a date and time.

| Field | Missing | Parse failures | Earliest | Latest |
| --- | --- | --- | --- | --- |
| order_purchase_timestamp | 0 | 0 | 2016-09-04 21:15:19 | 2018-10-17 17:30:18 |
| order_approved_at | 160 | 0 | 2016-09-15 12:16:38 | 2018-09-03 17:40:06 |
| order_delivered_carrier_date | 1,783 | 0 | 2016-10-08 10:34:01 | 2018-09-11 19:48:28 |
| order_delivered_customer_date | 2,965 | 0 | 2016-10-11 13:46:32 | 2018-10-17 13:22:46 |
| order_estimated_delivery_date | 0 | 0 | 2016-09-30 00:00:00 | 2018-11-12 00:00:00 |
| shipping_limit_date | 0 | 0 | 2016-09-19 00:15:34 | 2020-04-09 22:35:08 |

Each rule compares rows with both timestamps available. A row can break more than one rule. The estimated delivery date is compared at calendar-day precision.

| Chronology check | Unit | Comparable rows | Rows flagged |
| --- | --- | --- | --- |
| Approval before purchase | orders | 99,281 | 0 |
| Carrier handoff before purchase | orders | 97,658 | 166 |
| Carrier handoff before approval | orders | 97,644 | 1,359 |
| Customer delivery before purchase | orders | 96,476 | 0 |
| Customer delivery before approval | orders | 96,462 | 61 |
| Customer delivery before carrier handoff | orders | 96,475 | 23 |
| Estimated delivery day before purchase day | orders | 99,441 | 0 |
| Shipping limit before purchase | item rows | 112,650 | 0 |
| Shipping limit before approval | item rows | 112,635 | 127 |

An event recorded before purchase or out of the expected fulfillment order is a chronology conflict in the source. The dates alone cannot establish which field is wrong. A shipping limit is a deadline. A deadline before approval could reflect late approval or an issue in either field, so it is reported separately from the event sequence.

**4 item rows have a shipping limit more than 365 days after purchase.** The longest interval is 1,056 whole days. The 365-day threshold highlights unusually long intervals for review and is used only for this assessment.

## Order item uniqueness and candidate keys

The 112,650 item rows cover 98,666 distinct orders, including 9,803 orders with multiple items. There are 21 distinct `order_item_id` values across the file. An item number is meaningful within its order. The pair `(order_id, order_item_id)` is the candidate row identifier checked below. Repeat keys count occurrences after the first.

| Dataset | Candidate key | Rows missing a key field | Repeat complete keys | Result |
| --- | --- | --- | --- | --- |
| customers | customer_id | 0 | 0 | Unique and present |
| orders | order_id | 0 | 0 | Unique and present |
| order_items | order_id, order_item_id | 0 | 0 | Unique and present |
| products | product_id | 0 | 0 | Unique and present |
| sellers | seller_id | 0 | 0 | Unique and present |
| category_translations | product_category_name | 0 | 0 | Unique and present |

## Merchandise price and freight

| Field | Missing | Nonnumeric | Infinite | Negative | Zero | Min finite | Max finite |
| --- | --- | --- | --- | --- | --- | --- | --- |
| price | 0 | 0 | 0 | 0 | 0 | 0.85 | 6,735.00 |
| freight_value | 0 | 0 | 0 | 0 | 383 | 0.00 | 409.68 |

Negative merchandise or freight amounts would be unexpected for these item fields. Zero freight can represent no shipping charge. A zero merchandise price would need context, such as evidence of a free item. This check applies no upper price cutoff.

## Missing product categories and translations

| Coverage gap | Product rows | Linked item rows |
| --- | --- | --- |
| Blank category | 610 | 1,603 |
| Named category absent from lookup | 13 | 24 |

| Untranslated Portuguese category | Product rows |
| --- | --- |
| portateis_cozinha_e_preparadores_de_alimentos | 10 |
| pc_gamer | 3 |

Keep the distinction between an unknown category and a known category without an English label. Either gap can affect category summaries while the product ID still joins to its item rows.

## Referential integrity

A referencing value should appear in its lookup file. Missing references and nonblank values absent from the lookup are counted separately. Orders that have no item rows appear as lookup IDs with no rows because items point to orders.

| Referencing column | Lookup column | Missing references | Unmatched nonblank references | Lookup IDs with no rows | Lookup IDs with multiple rows |
| --- | --- | --- | --- | --- | --- |
| orders.customer_id | customers.customer_id | 0 | 0 | 0 | 0 |
| order_items.order_id | orders.order_id | 0 | 0 | 775 | 9,803 |
| order_items.product_id | products.product_id | 0 | 0 | 0 | 14,834 |
| order_items.seller_id | sellers.seller_id | 0 | 0 | 0 | 2,586 |
| products.product_category_name | category_translations.product_category_name | 610 | 13 | 0 | 70 |

## Decisions that need review before cleaning

- Decide how to handle contradictory or missing fulfillment timestamps in metrics that require those dates. The source cannot identify the correct event time.
- Define which order statuses qualify as purchases. Orders without items have no merchandise value available from the items file. Their order records provide lifecycle context.
- Decide how to label blank product categories and how to display categories with no English translation.

## Reproduce the assessment

From the project root in PowerShell, run:

```powershell
.\.venv\Scripts\python.exe -B .\src\ingestion\assess_data_quality.py
```

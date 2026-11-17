# Olist RFM customer segmentation

RFM describes how recently, how often, and how much each customer purchased. The input is the cleaned order flag `is_qualifying_purchase`, which selects delivered orders with item rows. The output has one row per `customer_unique_id`.

## Metrics and score bands

The reference date is **2018-08-30**, one day after the last qualifying purchase date (2018-08-29). Recency uses calendar days from the last qualifying purchase to the reference date.

| Metric | Score 1 | Score 2 | Score 3 |
| --- | --- | --- | --- |
| Recency in days | 181 or more | 91 to 180 | 1 to 90 |
| Frequency in distinct orders | 1 | 2 | 3 or more |
| Merchandise value | Below 60.00 | 60.00 to 129.99 | 130.00 or more |

Frequency counts each order once, including orders with multiple items. Monetary value sums qualifying item prices in integer cents and excludes freight. The recency bands use 90-day steps. Most customers bought once, so frequency uses order counts directly. The monetary cutoffs are rounded values near the lower and upper thirds of spending in this dataset. They are fixed for this run.

## Segment rules

| Segment | Rule | Meaning |
| --- | --- | --- |
| Champions | Purchased within 90 days, made at least two orders, and spent at least 130.00 | Recent repeat buyers with high merchandise value |
| Loyal Customers | Repeat buyers within 180 days, with Champions assigned first | Repeat buyers with recent or moderately recent activity |
| Potential Loyalists | One order within 90 days | Recent first-time buyers |
| At Risk | One order 91 to 180 days ago, or repeat buyers with no purchase in 180 days | Customers with a longer gap since their last order |
| Lost Customers | One order more than 180 days ago | Older one-time buyers in the observed data |

Each customer receives one segment. The labels describe observed purchase history.

## Results

The analysis covers **93,358 customers**, **96,478 qualifying orders**, and **13,221,498.11** in merchandise value.

| Segment | Customers | Share | Merchandise value |
| --- | --- | --- | --- |
| Champions | 424 | 0.45% | 148,611.07 |
| Loyal Customers | 806 | 0.86% | 182,415.64 |
| Potential Loyalists | 17,779 | 19.04% | 2,457,375.20 |
| At Risk | 20,539 | 22.00% | 3,095,322.37 |
| Lost Customers | 53,810 | 57.64% | 7,337,773.83 |

To check these totals, compare the sum of frequency and merchandise value with the monthly sales totals and compare the number of customers with frequency at least two with the repeat customer count. [SQL analysis](sql_analysis.md)

## Reproduce

From the project root in PowerShell, run the following command.

```powershell
.\.venv\Scripts\python.exe -B -m src.analysis.rfm
```

The script writes `data/processed/rfm_customers.csv` and this report. The CSV includes the last purchase date, raw metrics, scores, and segment for each customer.

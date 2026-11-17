# Olist monthly cohort retention

A cohort groups customers whose first qualifying purchase fell in the same calendar month. The analysis uses the same delivered orders with items as [RFM segmentation](rfm_analysis.md).

## How retention is calculated

1. Find the first qualifying purchase month for each `customer_unique_id` using the full purchase history in the files.
2. Count each customer once per calendar month with a qualifying purchase, even if they placed several orders that month.
3. Measure the month offset from the first purchase month. Month 0 is the starting cohort, and Month 1 is the next calendar month.
4. Divide the number of active customers in each month by the original cohort size. A customer can buy in Month 2 after skipping Month 1 and still count in Month 2.

## Observation window

Qualifying purchases run from **2016-09-15** through **2018-08-29**. The tables cover **2016-10 through 2018-07**. If the first or last qualifying date falls partway through its month, the analysis treats that boundary month as partial. This conservative rule uses the observed purchase dates because the files give no explicit coverage cutoff.

The published cohorts contain **87,213 of 93,358 customers**. The number excluded was 1 at the start and 6,144 at the end. Customer assignment uses the full history, so returning buyers from the partial starting month stay in their original cohort.

A zero means the month was inside the window and the cohort had no qualifying buyers that month. A blank means the month falls after the cutoff. A calendar month with no new customers has no cohort row and can still count as a month of follow-up.

## Results

Across cohorts with a full Month 1, **390 of 81,264 customers (0.48%)** made a qualifying purchase in the next calendar month.

| Example cohort | Starting customers | Month 1 buyers | Month 1 retention |
| --- | --- | --- | --- |
| 2016-10 | 262 | 0 | 0.00% |
| 2016-12 | 1 | 1 | 100.00% |
| 2017-11 | 7,060 | 40 | 0.57% |
| 2018-07 | 5,949 | Outside window | — |

The denominator stays fixed at the original cohort size. Month 0 is 100% for each cohort. The summary above divides total Month 1 buyers by the combined size of the cohorts with a full Month 1, so larger cohorts contribute more to this rate. Read each percentage alongside its starting customer count, especially for small cohorts.

## Reproduce

From the project root in PowerShell, run the following command.

```powershell
.\.venv\Scripts\python.exe -B -m src.analysis.cohort_retention
```

The script writes `cohort_retention_counts.csv` and `cohort_retention_rates.csv` under `data/processed/`. Both are organized by cohort month and month offset. Rates are recorded as percentages on a 0–100 scale.

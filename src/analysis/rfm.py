"""Calculate customer RFM scores from the cleaned Olist CSVs."""

from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from src.ingestion.explore_dataset import DATASETS, ROOT, markdown_table


PROCESSED = ROOT / "data" / "processed"
RESULT_PATH = PROCESSED / "rfm_customers.csv"
REPORT_PATH = ROOT / "docs" / "rfm_analysis.md"
SEGMENTS = ("Champions", "Loyal Customers", "Potential Loyalists", "At Risk", "Lost Customers")


def read_columns(dataset, columns, source_dir):
    filename = DATASETS[dataset][0]
    return pd.read_csv(source_dir / filename, usecols=columns, dtype=str, keep_default_na=False)


def load_qualifying_orders(source_dir=PROCESSED):
    """Return one row per qualifying order with a stable customer ID and purchase date."""
    orders = read_columns(
        "orders", ["order_id", "customer_id", "order_purchase_timestamp", "is_qualifying_purchase"],
        source_dir,
    )
    if not orders["is_qualifying_purchase"].isin(["True", "False"]).all():
        raise ValueError("Expected True or False in is_qualifying_purchase.")
    qualifying = orders.loc[orders["is_qualifying_purchase"].eq("True")].drop(
        columns="is_qualifying_purchase"
    )
    if qualifying.empty:
        raise ValueError("The cleaned orders file has no qualifying purchases.")

    customers = read_columns("customers", ["customer_id", "customer_unique_id"], source_dir)
    result = qualifying.merge(customers, on="customer_id", how="left", validate="many_to_one")
    if result["order_id"].eq("").any() or result["order_id"].duplicated().any():
        raise ValueError("Each qualifying order must have a unique order ID.")
    if result["customer_unique_id"].fillna("").eq("").any() or result["customer_id"].eq("").any():
        raise ValueError("Each qualifying order must match a customer identity.")
    result["purchase_date"] = pd.to_datetime(
        result["order_purchase_timestamp"], format="%Y-%m-%d %H:%M:%S"
    ).dt.normalize()
    if result["purchase_date"].isna().any():
        raise ValueError("Each qualifying order must have a purchase date.")
    return result[["order_id", "customer_unique_id", "purchase_date"]]


def load_order_spend(orders, source_dir=PROCESSED):
    """Return merchandise value in cents for each qualifying order."""
    items = read_columns("order_items", ["order_id", "price"], source_dir)
    items = items.loc[items["order_id"].isin(orders["order_id"])].copy()
    if not items["price"].str.fullmatch(r"[0-9]+\.[0-9]{2}").all():
        raise ValueError("Expected nonnegative item prices with two decimal places.")
    # Integer cents keep sums and score thresholds exact.
    items["monetary_cents"] = items["price"].str.replace(".", "", regex=False).astype("int64")
    order_spend = items.groupby("order_id")["monetary_cents"].sum()
    if not orders["order_id"].isin(order_spend.index).all():
        raise ValueError("Each qualifying order must have at least one priced item.")
    return order_spend


def calculate_rfm(orders, source_dir=PROCESSED):
    purchases = orders.join(load_order_spend(orders, source_dir), on="order_id", validate="one_to_one")
    reference_date = purchases["purchase_date"].max() + pd.Timedelta(days=1)
    result = purchases.groupby("customer_unique_id", as_index=False).agg(
        last_purchase_date=("purchase_date", "max"),
        frequency=("order_id", "nunique"),
        monetary_cents=("monetary_cents", "sum"),
    )
    result["recency_days"] = (reference_date - result["last_purchase_date"]).dt.days
    result["r_score"] = pd.cut(result["recency_days"], [0, 90, 180, float("inf")], labels=[3, 2, 1], ordered=False)
    result["f_score"] = result["frequency"].clip(upper=3)
    result["m_score"] = pd.cut(result["monetary_cents"], [0, 6000, 13000, float("inf")], labels=[1, 2, 3], right=False)

    recent = result["r_score"].eq(3)
    inactive = result["r_score"].eq(1)
    repeat = result["f_score"].ge(2)
    segment = pd.Series("At Risk", index=result.index, dtype="string")
    segment = segment.mask(inactive & ~repeat, "Lost Customers")
    segment = segment.mask(recent & ~repeat, "Potential Loyalists")
    segment = segment.mask(~inactive & repeat, "Loyal Customers")
    result["segment"] = segment.mask(recent & repeat & result["m_score"].eq(3), "Champions")
    return result, reference_date


def money(cents):
    return f"{cents // 100:,}.{cents % 100:02d}"


def build_report(result, reference_date):
    summary = result.groupby("segment").agg(
        customers=("customer_unique_id", "size"),
        monetary_cents=("monetary_cents", "sum"),
    ).reindex(SEGMENTS, fill_value=0)
    rows = ((name, f"{count:,}", f"{count / len(result):.2%}", money(cents))
            for name, count, cents in summary.itertuples())
    return "\n".join([
        "# Olist RFM customer segmentation",
        "",
        "RFM describes how recently, how often, and how much each customer purchased. "
        "The input is the cleaned order flag `is_qualifying_purchase`, which selects "
        "delivered orders with item rows. The output has one row per `customer_unique_id`.",
        "",
        "## Metrics and score bands",
        "",
        f"The reference date is **{reference_date:%Y-%m-%d}**, one day after the last qualifying "
        f"purchase date ({result['last_purchase_date'].max():%Y-%m-%d}). "
        "Recency uses calendar days from the last qualifying purchase to the reference date.",
        "",
        "| Metric | Score 1 | Score 2 | Score 3 |",
        "| --- | --- | --- | --- |",
        "| Recency in days | 181 or more | 91 to 180 | 1 to 90 |",
        "| Frequency in distinct orders | 1 | 2 | 3 or more |",
        "| Merchandise value | Below 60.00 | 60.00 to 129.99 | 130.00 or more |",
        "",
        "Frequency counts each order once, including orders with multiple items. Monetary "
        "value sums qualifying item prices in integer cents and excludes freight. "
        "The recency bands use 90-day steps. Most customers bought once, so frequency "
        "uses order counts directly. The monetary cutoffs are rounded values near the "
        "lower and upper thirds of spending in this dataset. They are fixed for this run.",
        "",
        "## Segment rules",
        "",
        "| Segment | Rule | Meaning |",
        "| --- | --- | --- |",
        "| Champions | Purchased within 90 days, made at least two orders, and spent at least 130.00 | Recent repeat buyers with high merchandise value |",
        "| Loyal Customers | Repeat buyers within 180 days, with Champions assigned first | Repeat buyers with recent or moderately recent activity |",
        "| Potential Loyalists | One order within 90 days | Recent first-time buyers |",
        "| At Risk | One order 91 to 180 days ago, or repeat buyers with no purchase in 180 days | Customers with a longer gap since their last order |",
        "| Lost Customers | One order more than 180 days ago | Older one-time buyers in the observed data |",
        "",
        "Each customer receives one segment. The labels describe observed purchase history.",
        "",
        "## Results",
        "",
        f"The analysis covers **{len(result):,} customers**, **{result['frequency'].sum():,} "
        f"qualifying orders**, and **{money(result['monetary_cents'].sum())}** in merchandise value.",
        "",
        markdown_table(["Segment", "Customers", "Share", "Merchandise value"], rows),
        "",
        "To check these totals, compare the sum of frequency and merchandise value with "
        "the monthly sales totals and compare the number of customers with frequency at least "
        "two with the repeat customer count. [SQL analysis](sql_analysis.md)",
        "",
        "## Reproduce",
        "",
        "From the project root in PowerShell, run the following command.",
        "",
        "```powershell",
        ".\\.venv\\Scripts\\python.exe -B -m src.analysis.rfm",
        "```",
        "",
        "The script writes `data/processed/rfm_customers.csv` and this report. "
        "The CSV includes the last purchase date, raw metrics, scores, and segment for each customer.",
        "",
    ])


def main():
    try:
        result, reference_date = calculate_rfm(load_qualifying_orders())
        report = build_report(result, reference_date)
        export = result.assign(monetary_value=result["monetary_cents"].map(lambda cents: money(cents).replace(",", "")))
        columns = ["customer_unique_id", "last_purchase_date", "recency_days", "frequency",
                   "monetary_value", "r_score", "f_score", "m_score", "segment"]
        with TemporaryDirectory(dir=ROOT, prefix=".olist-rfm-") as directory:
            stage = Path(directory)
            staged_csv = stage / RESULT_PATH.name
            staged_report = stage / REPORT_PATH.name
            export.to_csv(staged_csv, columns=columns, index=False, date_format="%Y-%m-%d")
            staged_report.write_text(report, encoding="utf-8")
            staged_csv.replace(RESULT_PATH)
            staged_report.replace(REPORT_PATH)
    except (ValueError, KeyError, OSError) as error:
        raise SystemExit(f"RFM analysis failed: {error}") from error
    print(f"Scored {len(result):,} customers as of {reference_date:%Y-%m-%d}.")
    print(f"Saved results to {RESULT_PATH} and report to {REPORT_PATH}")


if __name__ == "__main__":
    main()

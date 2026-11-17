"""Calculate monthly customer cohort counts and retention from Olist orders."""

from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from src.analysis.rfm import PROCESSED, load_qualifying_orders
from src.ingestion.explore_dataset import ROOT, markdown_table


COUNTS_PATH = PROCESSED / "cohort_retention_counts.csv"
RATES_PATH = PROCESSED / "cohort_retention_rates.csv"
REPORT_PATH = ROOT / "docs" / "cohort_analysis.md"


def calculate_cohorts(orders):
    customer_months = orders[["customer_unique_id"]].assign(
        purchase_month=orders["purchase_date"].dt.to_period("M")
    ).drop_duplicates()
    customer_months["cohort_month"] = customer_months.groupby(
        "customer_unique_id"
    )["purchase_month"].transform("min")

    first_day, last_day = orders["purchase_date"].min(), orders["purchase_date"].max()
    first_month = first_day.to_period("M") + int(not first_day.is_month_start)
    last_month = last_day.to_period("M") - int(not last_day.is_month_end)
    if first_month > last_month:
        raise ValueError("The qualifying orders do not span a complete calendar month.")

    cohort_sizes = customer_months.loc[
        customer_months["purchase_month"].eq(customer_months["cohort_month"])
    ].groupby("cohort_month").size()
    observed = customer_months.loc[
        customer_months["cohort_month"].ge(first_month)
        & customer_months["purchase_month"].le(last_month)
    ].copy()
    if observed.empty:
        raise ValueError("No customers first purchased in the published cohort window.")

    purchase, origin = observed["purchase_month"].dt, observed["cohort_month"].dt
    observed["month_offset"] = 12 * (purchase.year - origin.year) + purchase.month - origin.month

    counts = observed.groupby(["cohort_month", "month_offset"]).size().unstack(fill_value=0)
    max_offset = last_month.ordinal - counts.index.min().ordinal
    counts = counts.reindex(columns=range(max_offset + 1), fill_value=0)
    # A fully observed month with no buyers is zero. Months beyond the cutoff are blank.
    in_window = pd.DataFrame(
        {offset: counts.index + offset <= last_month for offset in counts}, index=counts.index
    )
    counts = counts.where(in_window).astype("Int64")
    if not counts[0].astype("int64").equals(cohort_sizes.reindex(counts.index)):
        raise ValueError("Month 0 does not reconcile to the number of customers in each cohort.")
    if counts.gt(counts[0], axis=0).any().any():
        raise ValueError("A month has more active customers than its starting cohort.")

    coverage = {
        "first_day": first_day, "last_day": last_day,
        "first_month": first_month, "last_month": last_month,
        "early_customers": cohort_sizes[cohort_sizes.index < first_month].sum(),
        "late_customers": cohort_sizes[cohort_sizes.index > last_month].sum(),
        "all_customers": cohort_sizes.sum(),
    }
    return counts, coverage


def as_export(matrix, cohort_sizes):
    export = matrix.rename(columns=lambda offset: f"month_{offset}")
    export.insert(0, "cohort_size", cohort_sizes)
    return export


def build_report(counts, rates, coverage):
    sizes = counts[0]
    sample_months = sorted({counts.index.min(), sizes.idxmin(), sizes.idxmax(), counts.index.max()})
    examples = []
    for month in sample_months:
        month_one = counts.at[month, 1] if 1 in counts else pd.NA
        active = f"{month_one:,}" if pd.notna(month_one) else "Outside window"
        rate = f"{rates.at[month, 1]:.2f}%" if pd.notna(month_one) else "—"
        examples.append((month, f"{sizes.at[month]:,}", active, rate))

    eligible = counts[1].notna() if 1 in counts else pd.Series(False, index=counts.index)
    month_one_buyers = counts.loc[eligible, 1].sum() if eligible.any() else 0
    eligible_buyers = sizes[eligible].sum()
    if eligible_buyers:
        month_one_summary = (
            f"Across cohorts with a full Month 1, **{month_one_buyers:,} of "
            f"{eligible_buyers:,} customers ({month_one_buyers / eligible_buyers:.2%})** "
            "made a qualifying purchase in the next calendar month."
        )
    else:
        month_one_summary = "The published cohorts have no fully observed Month 1."

    return "\n\n".join([
        "# Olist monthly cohort retention",
        "A cohort groups customers whose first qualifying purchase fell in the same calendar "
        "month. The analysis uses the same delivered orders with items as "
        "[RFM segmentation](rfm_analysis.md).",
        "## How retention is calculated",
        "1. Find the first qualifying purchase month for each `customer_unique_id` using the full purchase history in the files.\n"
        "2. Count each customer once per calendar month with a qualifying purchase, even if they placed several orders that month.\n"
        "3. Measure the month offset from the first purchase month. Month 0 is the starting cohort, and Month 1 is the next calendar month.\n"
        "4. Divide the number of active customers in each month by the original cohort size. "
        "A customer can buy in Month 2 after skipping Month 1 and still count in Month 2.",
        "## Observation window",
        f"Qualifying purchases run from **{coverage['first_day']:%Y-%m-%d}** through "
        f"**{coverage['last_day']:%Y-%m-%d}**. The tables cover **{coverage['first_month']} "
        f"through {coverage['last_month']}**. If the first or last qualifying date falls partway "
        "through its month, the analysis treats that boundary month as partial. This conservative "
        "rule uses the observed purchase dates because the files give no explicit coverage cutoff.",
        f"The published cohorts contain **{sizes.sum():,} of {coverage['all_customers']:,} customers**. "
        f"The number excluded was {coverage['early_customers']:,} at the start and "
        f"{coverage['late_customers']:,} at the end. Customer assignment uses the "
        "full history, so returning buyers from the partial starting month stay in their original cohort.",
        "A zero means the month was inside the window and the cohort had no qualifying buyers that "
        "month. A blank means the month falls after the cutoff. A calendar month with no new "
        "customers has no cohort row and can still count as a month of follow-up.",
        "## Results",
        month_one_summary,
        markdown_table(["Example cohort", "Starting customers", "Month 1 buyers", "Month 1 retention"], examples),
        "The denominator stays fixed at the original cohort size. Month 0 is 100% for each cohort. "
        "The summary above divides total Month 1 buyers by the combined size of the cohorts with "
        "a full Month 1, so larger cohorts contribute more to this rate. "
        "Read each percentage alongside its starting customer count, especially for small cohorts.",
        "## Reproduce",
        "From the project root in PowerShell, run the following command.",
        "```powershell\n.\\.venv\\Scripts\\python.exe -B -m src.analysis.cohort_retention\n```",
        "The script writes `cohort_retention_counts.csv` and `cohort_retention_rates.csv` "
        "under `data/processed/`. Both are organized by cohort month and month offset. "
        "Rates are recorded as percentages on a 0–100 scale.",
    ]) + "\n"


def main():
    try:
        counts, coverage = calculate_cohorts(load_qualifying_orders())
        rates = counts.div(counts[0], axis=0).mul(100)
        report = build_report(counts, rates, coverage)
        with TemporaryDirectory(dir=ROOT, prefix=".olist-cohort-") as directory:
            stage = Path(directory)
            as_export(counts, counts[0]).to_csv(stage / COUNTS_PATH.name, index_label="cohort_month")
            as_export(rates, counts[0]).to_csv(
                stage / RATES_PATH.name, index_label="cohort_month", float_format="%.4f"
            )
            (stage / REPORT_PATH.name).write_text(report, encoding="utf-8")
            for target in (COUNTS_PATH, RATES_PATH, REPORT_PATH):
                (stage / target.name).replace(target)
    except (ValueError, KeyError, OSError) as error:
        raise SystemExit(f"Cohort analysis failed: {error}") from error
    print(f"Wrote {len(counts)} cohorts with {counts[0].sum():,} customers.")
    print(f"Saved {COUNTS_PATH.name}, {RATES_PATH.name}, and {REPORT_PATH}")


if __name__ == "__main__":
    main()

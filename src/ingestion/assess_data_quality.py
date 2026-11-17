"""Assess the six raw Olist CSVs and generate the Milestone 1 report."""

import pandas as pd

from explore_dataset import ROOT, key_checks, load_datasets, markdown_table, relationship_checks


REPORT_PATH = ROOT / "docs" / "data_quality_assessment.md"
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"
ORDER_DATES = {
    "purchase": "order_purchase_timestamp",
    "approval": "order_approved_at",
    "carrier handoff": "order_delivered_carrier_date",
    "customer delivery": "order_delivered_customer_date",
    "estimated delivery": "order_estimated_delivery_date",
}


def customer_identity(customers, orders):
    links = customers[["customer_id", "customer_unique_id"]].dropna()
    identities_per_id = links.groupby("customer_id")["customer_unique_id"].nunique()
    ids_per_identity = links.groupby("customer_unique_id")["customer_id"].nunique()
    orders_per_id = orders.groupby("customer_id")["order_id"].nunique()
    return "\n".join([
        f"- Customer rows: {len(customers):,}. Distinct `customer_id` values: "
        f"{customers['customer_id'].nunique():,}. Distinct `customer_unique_id` values: "
        f"{customers['customer_unique_id'].nunique():,}.",
        f"- Missing `customer_unique_id`: {customers['customer_unique_id'].isna().sum():,}. "
        f"Customer IDs pointing to multiple identities: {identities_per_id.gt(1).sum():,}. "
        f"Customer IDs used by multiple orders: {orders_per_id.gt(1).sum():,}.",
        f"- Customer identities mapped to more than one `customer_id`: "
        f"{ids_per_identity.gt(1).sum():,}. Largest number of customer IDs per identity: "
        f"{ids_per_identity.max():,}.",
        "",
        "Use `customer_id` to connect an order to its customer record. "
        "Use `customer_unique_id` to count customers across orders. Repeated values "
        "of `customer_unique_id` are consistent with the dataset's identity model.",
    ])


def order_status_checks(orders, items):
    status = orders["order_status"]
    no_items = ~orders["order_id"].isin(items["order_id"].dropna())
    summary = pd.DataFrame({
        "orders": 1,
        "no items": no_items,
        "missing approval": orders[ORDER_DATES["approval"]].isna(),
        "missing carrier handoff": orders[ORDER_DATES["carrier handoff"]].isna(),
        "missing customer delivery": orders[ORDER_DATES["customer delivery"]].isna(),
    }).groupby(status, dropna=False).sum().sort_values("orders", ascending=False)
    table = markdown_table(
        ["Order status", "Orders", "Share", "Without items",
         "Missing approval", "Missing handoff", "Missing delivery"],
        (("(missing)" if pd.isna(label) else label, f"{total:,}", f"{total / len(orders):.2%}",
          *(f"{count:,}" for count in counts))
         for label, total, *counts in summary.itertuples()),
    )
    delivered = status.eq("delivered")
    canceled_with_delivery = status.eq("canceled") & orders[ORDER_DATES["customer delivery"]].notna()
    return "\n\n".join([
        table,
        f"**{no_items.sum():,} orders have no item rows**, including "
        f"{(no_items & delivered).sum():,} marked delivered. An order can be recorded before "
        "its items become available, and cancellation or unavailability can interrupt fulfillment. "
        "The statuses provide context for the gaps. The source does not establish each cause.",
        f"**{canceled_with_delivery.sum():,} canceled orders have a customer delivery timestamp.** "
        "Delivered orders with missing timestamps and canceled orders with recorded delivery need "
        "review before using those fields as proof of a fulfillment event.",
    ])


def timestamp_checks(orders, items):
    parsed = {}
    coverage = []
    fields = [(label, orders[column], column) for label, column in ORDER_DATES.items()]
    fields.append(("shipping limit", items["shipping_limit_date"], "shipping_limit_date"))
    for label, values, column in fields:
        dates = pd.to_datetime(values, format=TIMESTAMP_FORMAT, errors="coerce")
        parsed[label] = dates
        coverage.append((
            column, f"{values.isna().sum():,}", f"{(values.notna() & dates.isna()).sum():,}",
            dates.min(), dates.max(),
        ))

    checks = [
        ("Approval before purchase", "orders", parsed["approval"], parsed["purchase"]),
        ("Carrier handoff before purchase", "orders", parsed["carrier handoff"], parsed["purchase"]),
        ("Carrier handoff before approval", "orders", parsed["carrier handoff"], parsed["approval"]),
        ("Customer delivery before purchase", "orders", parsed["customer delivery"], parsed["purchase"]),
        ("Customer delivery before approval", "orders", parsed["customer delivery"], parsed["approval"]),
        ("Customer delivery before carrier handoff", "orders",
         parsed["customer delivery"], parsed["carrier handoff"]),
        ("Estimated delivery day before purchase day", "orders",
         parsed["estimated delivery"].dt.normalize(), parsed["purchase"].dt.normalize()),
    ]

    # Match only order IDs that identify a single order for the item-level comparisons.
    unique_order = orders["order_id"].notna() & ~orders["order_id"].duplicated(keep=False)
    item_order_dates = {}
    for label in ("purchase", "approval"):
        order_dates = parsed[label][unique_order].set_axis(orders.loc[unique_order, "order_id"])
        item_order_dates[label] = items["order_id"].map(order_dates)
        checks.append((f"Shipping limit before {label}", "item rows",
                       parsed["shipping limit"], item_order_dates[label]))

    chronology = []
    for rule, unit, later, earlier in checks:
        comparable = later.notna() & earlier.notna()
        chronology.append((rule, unit, f"{comparable.sum():,}", f"{(later < earlier).sum():,}"))

    shipping_lead = parsed["shipping limit"] - item_order_dates["purchase"]
    long_lead_count = shipping_lead.gt(pd.Timedelta(days=365)).sum()
    max_lead = shipping_lead.max()
    longest = f"{max_lead.days:,} whole days" if pd.notna(max_lead) else "unavailable"

    return "\n\n".join([
        "Timestamp strings were parsed in memory using `YYYY-MM-DD HH:MM:SS`. "
        "The CSVs supply no time-zone offset, so the comparisons use the recorded clock values. "
        "A parse failure is a populated value that could not be read as a date and time.",
        markdown_table(["Field", "Missing", "Parse failures", "Earliest", "Latest"], coverage),
        "Each rule compares rows with both timestamps available. A row can break more than "
        "one rule. The estimated delivery date is compared at calendar-day precision.",
        markdown_table(["Chronology check", "Unit", "Comparable rows", "Rows flagged"], chronology),
        "An event recorded before purchase or out of the expected fulfillment order is a "
        "chronology conflict in the source. The dates alone cannot establish which field is wrong. "
        "A shipping limit is a deadline. A deadline before approval could reflect late approval "
        "or an issue in either field, so it is reported separately from the event sequence.",
        f"**{long_lead_count:,} item rows have a shipping limit more than 365 days after purchase.** "
        f"The longest interval is {longest}. The 365-day threshold highlights unusually long "
        "intervals for review and is used only for this assessment.",
    ])


def item_value_checks(items):
    rows = []
    for column in ("price", "freight_value"):
        source = items[column]
        numeric = pd.to_numeric(source, errors="coerce")
        nonfinite = numeric.isin([float("-inf"), float("inf")])
        finite = numeric[numeric.notna() & ~nonfinite]
        rows.append((
            column, f"{source.isna().sum():,}", f"{(source.notna() & numeric.isna()).sum():,}",
            f"{nonfinite.sum():,}", f"{finite.lt(0).sum():,}", f"{finite.eq(0).sum():,}",
            f"{finite.min():,.2f}", f"{finite.max():,.2f}",
        ))
    return "\n\n".join([
        markdown_table(
            ["Field", "Missing", "Nonnumeric", "Infinite", "Negative", "Zero", "Min finite", "Max finite"],
            rows,
        ),
        "Negative merchandise or freight amounts would be unexpected for these item fields. "
        "Zero freight can represent no shipping charge. A zero merchandise price would need "
        "context, such as evidence of a free item. This check applies no upper price cutoff.",
    ])


def category_coverage(products, translations, items):
    categories = products["product_category_name"]
    missing = categories.isna()
    has_translation = categories.isin(translations["product_category_name"].dropna())
    missing_translation = categories.notna() & ~has_translation
    breakdown = categories[missing_translation].value_counts()
    rows = []
    for label, affected in [("Blank category", missing), ("Named category absent from lookup", missing_translation)]:
        item_count = items["product_id"].isin(products.loc[affected, "product_id"].dropna()).sum()
        rows.append((label, f"{affected.sum():,}", f"{item_count:,}"))
    return "\n\n".join([
        markdown_table(["Coverage gap", "Product rows", "Linked item rows"], rows),
        markdown_table(["Untranslated Portuguese category", "Product rows"],
                       ((name, f"{count:,}") for name, count in breakdown.items())),
        "Keep the distinction between an unknown category and a known category without an "
        "English label. Either gap can affect category summaries while the product ID still "
        "joins to its item rows.",
    ])


def build_report(frames):
    orders = frames["orders"]
    items = frames["order_items"]
    item_counts = items.groupby("order_id").size()
    sections = [
        "# Olist data quality assessment",
        "Milestone 1 covers the six local CSVs described in the "
        "[dataset exploration report](dataset_exploration.md). The checks read the source files "
        "and write this report. Dates and amounts are parsed in memory for validation.",
        "## Customer identifiers",
        customer_identity(frames["customers"], orders),
        "## Order statuses and orders without items",
        order_status_checks(orders, items),
        "## Timestamps",
        timestamp_checks(orders, items),
        "## Order item uniqueness and candidate keys",
        f"The {len(items):,} item rows cover {len(item_counts):,} distinct orders, including "
        f"{item_counts.gt(1).sum():,} orders with multiple items. "
        f"There are {items['order_item_id'].nunique():,} distinct `order_item_id` values across the file. "
        "An item number is meaningful within its order. The pair `(order_id, order_item_id)` "
        "is the candidate row identifier checked below. Repeat keys count occurrences after the first.",
        key_checks(frames),
        "## Merchandise price and freight",
        item_value_checks(items),
        "## Missing product categories and translations",
        category_coverage(frames["products"], frames["category_translations"], items),
        "## Referential integrity",
        "A referencing value should appear in its lookup file. Missing references and "
        "nonblank values absent from the lookup are counted separately. Orders that have "
        "no item rows appear as lookup IDs with no rows because items point to orders.",
        relationship_checks(frames),
        "## Decisions that need review before cleaning",
        "- Decide how to handle contradictory or missing fulfillment timestamps in metrics "
        "that require those dates. The source cannot identify the correct event time.\n"
        "- Define which order statuses qualify as purchases. Orders without items have no "
        "merchandise value available from the items file. Their order records provide lifecycle context.\n"
        "- Decide how to label blank product categories and how to display categories with "
        "no English translation.",
        "## Reproduce the assessment",
        "From the project root in PowerShell, run:\n\n"
        "```powershell\n.\\.venv\\Scripts\\python.exe -B .\\src\\ingestion\\assess_data_quality.py\n```",
    ]
    return "\n\n".join(sections) + "\n"


def main():
    frames = load_datasets()
    required = {
        "orders": list(ORDER_DATES.values()),
        "order_items": ["shipping_limit_date", "price", "freight_value"],
    }
    for name, columns in required.items():
        missing = sorted(set(columns).difference(frames[name].columns))
        if missing:
            raise SystemExit(f"{name} is missing assessment columns: {', '.join(missing)}")
    REPORT_PATH.write_text(build_report(frames), encoding="utf-8")
    print(f"Assessed {len(frames)} CSVs. Report saved to {REPORT_PATH}")


if __name__ == "__main__":
    main()

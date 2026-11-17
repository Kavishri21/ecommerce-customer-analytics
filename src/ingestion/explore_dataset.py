"""Profile the six Olist CSVs and write the Markdown exploration report."""

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw"
REPORT_PATH = ROOT / "docs" / "dataset_exploration.md"

# Each entry names the source, describes what one row represents, and lists
# the columns that should identify a row.
DATASETS = {
    "customers": (
        "olist_customers_dataset.csv",
        "One customer record with a location and two customer identifiers.",
        ["customer_id"],
    ),
    "orders": (
        "olist_orders_dataset.csv",
        "One order with its customer ID, status, and timestamps.",
        ["order_id"],
    ),
    "order_items": (
        "olist_order_items_dataset.csv",
        "One item within an order, with its product, seller, price, and freight.",
        ["order_id", "order_item_id"],
    ),
    "products": (
        "olist_products_dataset.csv",
        "One product with its category and descriptive fields such as dimensions.",
        ["product_id"],
    ),
    "sellers": (
        "olist_sellers_dataset.csv",
        "One seller with its location.",
        ["seller_id"],
    ),
    "category_translations": (
        "product_category_name_translation.csv",
        "One Portuguese product category paired with its English label.",
        ["product_category_name"],
    ),
}

RELATIONSHIPS = (
    ("orders", "customer_id", "customers"),
    ("order_items", "order_id", "orders"),
    ("order_items", "product_id", "products"),
    ("order_items", "seller_id", "sellers"),
    ("products", "product_category_name", "category_translations"),
)


def load_datasets():
    missing = [filename for filename, _, _ in DATASETS.values()
               if not (RAW_DIR / filename).is_file()]
    if missing:
        raise SystemExit("Missing CSV files in data/raw/: " + ", ".join(missing))

    frames = {}
    for name, (filename, _, _) in DATASETS.items():
        try:
            frames[name] = pd.read_csv(RAW_DIR / filename)
        except (OSError, UnicodeError, pd.errors.ParserError, pd.errors.EmptyDataError) as error:
            raise SystemExit(f"Could not read {filename}: {error}") from error

    required_columns = {name: set(key) for name, (_, _, key) in DATASETS.items()}
    for child, column, parent in RELATIONSHIPS:
        required_columns[child].add(column)
        required_columns[parent].add(column)
    required_columns["customers"].add("customer_unique_id")
    required_columns["orders"].add("order_status")
    for name, required in required_columns.items():
        absent = required.difference(frames[name].columns)
        if absent:
            filename = DATASETS[name][0]
            raise SystemExit(f"{filename} is missing columns: {', '.join(sorted(absent))}")
    return frames


def markdown_table(headers, rows):
    def row(values):
        cells = [str(value).replace("\\", "\\\\").replace("|", "\\|")
                 .replace("\r\n", "<br>").replace("\n", "<br>").replace("\r", "<br>")
                 for value in values]
        return "| " + " | ".join(cells) + " |"

    return "\n".join([row(headers), row(["---"] * len(headers)),
                      *(row(values) for values in rows)])


def profile(filename, description, frame):
    schema = markdown_table(
        ["Column", "Pandas dtype", "Missing values"],
        ((column, dtype, f"{missing:,}") for column, dtype, missing in
         zip(frame.columns, frame.dtypes, frame.isna().sum())),
    )
    sample = frame.head(3)
    # Show records as columns so wide CSVs remain readable in Markdown.
    samples = markdown_table(
        ["Column", *(f"Record {number}" for number in range(1, len(sample) + 1))],
        ([column, *("(missing)" if pd.isna(value) else value for value in sample[column])]
         for column in sample.columns),
    )
    return "\n\n".join([
        f"### `{filename}`",
        description,
        f"**Rows:** {len(frame):,} · **Columns:** {len(frame.columns):,} · "
        f"**Duplicate rows:** {frame.duplicated().sum():,}",
        schema,
        "**First three records in CSV order**",
        samples,
    ])


def key_checks(frames):
    rows = []
    for name, (_, _, key) in DATASETS.items():
        values = frames[name][key]
        complete = values.dropna()
        missing = len(values) - len(complete)
        duplicates = complete.duplicated().sum()
        result = "Unique and present" if missing == 0 and duplicates == 0 else "Review needed"
        rows.append((name, ", ".join(key), f"{missing:,}", f"{duplicates:,}", result))
    return markdown_table(
        ["Dataset", "Candidate key", "Rows missing a key field", "Repeat complete keys", "Result"],
        rows,
    )


def relationship_checks(frames):
    rows = []
    for child, column, parent in RELATIONSHIPS:
        child_values = frames[child][column].dropna()
        parent_values = frames[parent][column].dropna().unique()
        matched = child_values.isin(parent_values)
        linked_rows = child_values[matched].value_counts()
        rows.append((
            f"{child}.{column}", f"{parent}.{column}",
            f"{len(frames[child]) - len(child_values):,}",
            f"{(~matched).sum():,}",
            f"{len(parent_values) - len(linked_rows):,}",
            f"{linked_rows.gt(1).sum():,}",
        ))
    return markdown_table(
        ["Referencing column", "Lookup column", "Missing references",
         "Unmatched nonblank references", "Lookup IDs with no rows",
         "Lookup IDs with multiple rows"],
        rows,
    )


def build_report(frames):
    customers = frames["customers"]
    orders = frames["orders"]
    items = frames["order_items"]
    customer_ids_per_person = customers.groupby("customer_unique_id")["customer_id"].nunique()
    orders_without_items = orders.loc[
        orders["order_id"].notna() & ~orders["order_id"].isin(items["order_id"]),
        "order_status",
    ]
    status_counts = orders_without_items.value_counts(dropna=False)
    statuses = ", ".join(
        f"{'(missing)' if pd.isna(status) else status} ({count:,})"
        for status, count in status_counts.items()
    )
    status_detail = f" Their recorded statuses were {statuses}." if statuses else ""

    sections = [
        "# Olist dataset exploration",
        "The report covers the six CSVs in `data/raw/`. It uses Pandas' default CSV "
        "type and missing-value detection. Timestamps appear as text, and numeric-looking "
        "ZIP prefixes may display without leading zeroes. Duplicate counts include each "
        "identical row after its first occurrence.",
        "## How the files relate",
        "- **Customers and orders.** Join on `customer_id` to find the customer record "
        "for an order. Use `customer_unique_id` to recognize the same customer across orders. "
        f"The customer file contains {customers['customer_id'].nunique():,} distinct "
        f"`customer_id` values and {len(customer_ids_per_person):,} distinct "
        f"`customer_unique_id` values, with {customer_ids_per_person.gt(1).sum():,} "
        "customer identities linked to multiple `customer_id` values. "
        f"The customer identity is missing on {customers['customer_unique_id'].isna().sum():,} rows.\n"
        "- **Orders and order items.** Orders describe the purchase as a whole. Order items "
        "describe individual entries within a purchase. Joining on `order_id` produces "
        "one result row per matching item, so order fields repeat for orders with several items. "
        "`order_item_id` is scoped to its order and is checked together with `order_id`. "
        f"{len(orders_without_items):,} order rows have no matching item rows.{status_detail}\n"
        "- **Products, sellers, and order items.** Each item supplies a `product_id` for "
        "product details and a `seller_id` for seller details. The same product or seller "
        "can appear on many item rows.\n"
        "- **Products and category translations.** Use `product_category_name` to attach "
        "an English category label where a translation exists. A blank product category and "
        "a named category without a translation are different cases.",
        "## Candidate primary keys",
        "A primary key identifies a row. A candidate passes this check when all of its "
        "fields are present on every row and each value or combination occurs once. "
        "A repeat is counted after the first occurrence of a complete key.",
        key_checks(frames),
        "## Candidate foreign keys",
        "A foreign key links a row to a lookup record. Missing references are blank according "
        "to Pandas. Unmatched nonblank references are rows with a value absent from the lookup. "
        "The final two columns count distinct lookup IDs and show how many are unused or reused.",
        relationship_checks(frames),
        "## Interpreting missing values",
        "A blank approval or delivery timestamp may reflect an order that never reached "
        "that stage or a timestamp that was never recorded. A blank product category "
        "leaves the English category unknown. These gaps should be interpreted using the "
        "surrounding fields and the intended analysis.",
        "## File profiles",
        *(profile(filename, description, frames[name])
          for name, (filename, description, _) in DATASETS.items()),
    ]
    return "\n\n".join(sections) + "\n"


def main():
    report = build_report(load_datasets())
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(f"Profiled {len(DATASETS)} CSVs. Report saved to {REPORT_PATH}")


if __name__ == "__main__":
    main()

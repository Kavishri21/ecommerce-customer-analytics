"""Run the Olist cleaning pipeline from the project root as a Python module."""

from pathlib import Path
from shutil import copy2
from tempfile import TemporaryDirectory

from src.ingestion.explore_dataset import DATASETS, ROOT, load_datasets, markdown_table
from src.processing.cleaning import TIMESTAMP_FORMAT, clean_datasets


OUTPUT_DIR = ROOT / "data" / "processed"
REPORT_PATH = ROOT / "docs" / "data_cleaning_report.md"


def build_report(raw, tables, trimmed):
    orders = tables["orders"]
    items = tables["order_items"]
    categories = tables["products"]["category_translation_status"].value_counts()
    metrics = (
        ("Qualifying purchases", orders["is_qualifying_purchase"].sum()),
        ("Orders without items", (~orders["has_order_items"]).sum()),
        ("Orders with a chronology conflict", orders["has_chronology_conflict"].sum()),
        ("Orders with a fulfillment status gap", orders["has_fulfillment_status_gap"].sum()),
        ("Item rows with a shipping deadline flagged for review", items["shipping_limit_needs_review"].sum()),
        ("Products with a blank category", categories.get("missing_category", 0)),
        ("Products with a named category and no English label", categories.get("translation_missing", 0)),
        ("Item rows with zero freight", items["freight_value"].eq("0.00").sum()),
    )
    file_rows = (
        (filename, f"{len(raw[name]):,}", f"{len(tables[name]):,}", f"{trimmed[name]:,}")
        for name, (filename, _, _) in DATASETS.items()
    )
    return "\n\n".join([
        "# Olist data cleaning and validation",
        "Milestone 2 applies the rules below to the six raw CSVs and saves six UTF-8 CSVs "
        "under `data/processed/`. The input findings are recorded in the "
        "[data quality assessment](data_quality_assessment.md).",
        "## Row counts",
        markdown_table(["Processed file", "Input rows", "Output rows", "Cells trimmed"], file_rows),
        "All six output row counts match their inputs. The whitespace count measures cells "
        "whose outer spaces were removed during import.",
        "## Cleaning rules",
        "- **Identifiers and ZIP prefixes.** Read source columns as text first. Validate Olist "
        "IDs as 32 lowercase hexadecimal characters. Store ZIP prefixes as five-character "
        "text, including leading zeroes. CSV stores characters, so readers should request "
        "a string dtype for these fields.\n"
        "- **Dates.** Write timestamps in `YYYY-MM-DD HH:MM:SS` format using the source clock. "
        "Purchase time is required. Missing optional dates stay blank. Chronology conflicts "
        "and unusual shipping deadlines keep their source values and get review flags.\n"
        "- **Numbers.** Store item positions as positive integers and product measurements "
        "and counts as nullable, nonnegative integers. Write price and freight as exact "
        "nonnegative decimal text with two decimal places. Zero amounts are allowed.\n"
        "- **Categories.** Keep the Portuguese category and add its English label where "
        "available. Use `category_translation_status` to distinguish `translated`, "
        "`missing_category`, and `translation_missing`. An unavailable English label stays blank.\n"
        "- **Orders.** A qualifying purchase is an order marked `delivered` with at least one "
        "item row. This is the project's purchase definition for customer analysis. The six "
        "files supply order status and item details. Every order stays available for lifecycle analysis.",
        "## Review flags and eligibility",
        markdown_table(["Measure", "Rows"], ((label, f"{count:,}") for label, count in metrics)),
        "- **`has_order_items`** shows whether an order has a matching item. "
        "**`is_qualifying_purchase`** applies the delivered-with-items rule.\n"
        "- **`has_chronology_conflict`** marks an order if approval, carrier handoff, or "
        "customer delivery contradicts the expected event sequence, or estimated delivery "
        "falls before the purchase day. A comparison requires both timestamps.\n"
        "- **`has_fulfillment_status_gap`** marks a delivered order missing approval, handoff, "
        "or delivery time, or a canceled order with a delivery time.\n"
        "- **`shipping_limit_needs_review`** marks an item when its deadline predates purchase "
        "or approval, or falls more than 365 days after purchase. The one-year threshold flags "
        "outliers for review. These flags can overlap and eligibility uses the order status and item match.",
        "## Validation before writing",
        "All six candidate keys passed completeness and uniqueness checks. "
        "All four required relationships passed: order to customer, and item to order, "
        "product, and seller. Category translation is an optional lookup.",
        "A missing or duplicate key, invalid populated date or numeric value, missing "
        "purchase timestamp or amount, unknown status, or broken required reference stops "
        "the run before publishing. The error identifies the affected check and row count. "
        "A break in date chronology instead produces a review flag because the correct event "
        "time cannot be recovered from these CSVs.",
        "## Run the pipeline",
        "From the project root in PowerShell, run",
        "```powershell\n.\\.venv\\Scripts\\python.exe -B -m src.processing.clean_dataset\n```",
    ]) + "\n"


def write_outputs(tables, report, output_dir, report_path):
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=ROOT, prefix=".olist-cleaning-") as directory:
        stage = Path(directory)
        files = []
        for name, (filename, _, _) in DATASETS.items():
            staged = stage / filename
            tables[name].to_csv(staged, index=False, encoding="utf-8", date_format=TIMESTAMP_FORMAT)
            files.append((staged, output_dir / filename))
        staged_report = stage / report_path.name
        staged_report.write_text(report, encoding="utf-8")
        files.append((staged_report, report_path))

        backups = {}
        for staged, destination in files:
            if destination.exists():
                backup = stage / f"{staged.name}.previous"
                copy2(destination, backup)
                backups[destination] = backup

        published = []
        try:
            for staged, destination in files:
                staged.replace(destination)
                published.append(destination)
        except OSError:
            for destination in reversed(published):
                if destination in backups:
                    backups[destination].replace(destination)
                else:
                    destination.unlink()
            raise


def main():
    raw = load_datasets(dtype=str, keep_default_na=False, na_values=[""])
    try:
        tables, trimmed = clean_datasets(raw)
        report = build_report(raw, tables, trimmed)
        write_outputs(tables, report, OUTPUT_DIR, REPORT_PATH)
    except (KeyError, ValueError, OSError) as error:
        raise SystemExit(f"Cleaning failed: {error}") from error
    print(f"Wrote {len(tables)} validated CSVs to {OUTPUT_DIR}")
    print(f"Report saved to {REPORT_PATH}")


if __name__ == "__main__":
    main()

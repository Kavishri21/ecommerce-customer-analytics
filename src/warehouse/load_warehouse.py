"""Load the cleaned Olist data into MySQL from the project root."""

import argparse
from datetime import date, timedelta
from decimal import Decimal

from mysql.connector import Error

from src.ingestion.explore_dataset import ROOT, load_datasets, markdown_table
from src.warehouse.connection import connect_to_mysql, mysql_settings


DIMENSIONS = {
    "customers": ("customer_id", "customer_unique_id", "customer_zip_code_prefix", "customer_city", "customer_state"),
    "products": ("product_id", "product_category_name", "product_category_name_english", "category_translation_status"),
    "sellers": ("seller_id", "seller_zip_code_prefix", "seller_city", "seller_state"),
}
FACT_COLUMNS = (
    "order_id", "order_item_id", "customer_key", "product_key", "seller_key",
    "purchase_date", "order_status", "price", "freight_value",
)
PRIMARY_KEYS = {
    "dim_customers": ("customer_key",),
    "dim_products": ("product_key",),
    "dim_sellers": ("seller_key",),
    "dim_date": ("full_date",),
    "fact_order_items": ("order_id", "order_item_id"),
}
FOREIGN_KEYS = {
    ("customer_key", "dim_customers", "customer_key"),
    ("product_key", "dim_products", "product_key"),
    ("seller_key", "dim_sellers", "seller_key"),
    ("purchase_date", "dim_date", "full_date"),
}
REPORT_PATH = ROOT / "docs" / "data_loading_report.md"
BATCH_SIZE = 1000


def prepare_data(frames):
    dimensions = {}
    for name, columns in DIMENSIONS.items():
        rows = frames[name][list(columns)].itertuples(index=False, name=None)
        dimensions[f"dim_{name}"] = (columns, [tuple(value or None for value in row) for row in rows])

    order_rows = frames["orders"][["order_id", "customer_id", "order_purchase_timestamp", "order_status"]]
    orders = {
        order_id: (customer_id, date.fromisoformat(purchase[:10]), status)
        for order_id, customer_id, purchase, status in order_rows.itertuples(index=False, name=None)
    }
    first_day = min(row[1] for row in orders.values())
    last_day = max(row[1] for row in orders.values())
    dates = (first_day + timedelta(days=offset) for offset in range((last_day - first_day).days + 1))
    dimensions["dim_date"] = (
        ("full_date", "calendar_year", "calendar_month"),
        [(day, day.year, day.month) for day in dates],
    )

    item_columns = ["order_id", "order_item_id", "product_id", "seller_id", "price", "freight_value"]
    items = [
        (order_id, int(position), product_id, seller_id, Decimal(price), Decimal(freight))
        for order_id, position, product_id, seller_id, price, freight in
        frames["order_items"][item_columns].itertuples(index=False, name=None)
    ]
    order_ids = {row[0] for row in items}
    qualifying = {order_id for order_id in order_ids if orders[order_id][2] == "delivered"}
    expected = {
        **{name: len(rows) for name, (_, rows) in dimensions.items()},
        "fact_order_items": len(items),
        "orders_with_items": len(order_ids),
        "qualifying_orders": len(qualifying),
        "qualifying_items": sum(row[0] in qualifying for row in items),
        "merchandise_total": sum(row[4] for row in items),
        "freight_total": sum(row[5] for row in items),
        "items_missing_a_dimension": 0,
    }
    return dimensions, orders, items, expected


def create_schema(cursor, database):
    # The database name is validated before it can be interpolated as an identifier.
    cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{database}` CHARACTER SET utf8mb4")
    cursor.execute(f"USE `{database}`")
    ddl = (ROOT / "sql" / "schema.sql").read_text(encoding="utf-8")
    for statement in ddl.split(";"):
        if statement.strip():
            cursor.execute(statement)


def verify_schema(cursor, database):
    cursor.execute("SELECT TABLE_NAME, ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA = %s", (database,))
    engines = {row["TABLE_NAME"]: row["ENGINE"] for row in cursor.fetchall()}
    if any(engines.get(table) != "InnoDB" for table in PRIMARY_KEYS):
        raise ValueError("The target needs all five warehouse tables with the InnoDB engine.")

    cursor.execute(
        "SELECT TABLE_NAME, CONSTRAINT_NAME, COLUMN_NAME, REFERENCED_TABLE_SCHEMA, "
        "REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME "
        "FROM information_schema.KEY_COLUMN_USAGE WHERE TABLE_SCHEMA = %s "
        "ORDER BY ORDINAL_POSITION", (database,),
    )
    keys = cursor.fetchall()
    for table, expected in PRIMARY_KEYS.items():
        actual = tuple(row["COLUMN_NAME"] for row in keys
                       if row["TABLE_NAME"] == table and row["CONSTRAINT_NAME"] == "PRIMARY")
        if actual != expected:
            raise ValueError(f"{table} has an unexpected primary key.")
    for name, columns in DIMENSIONS.items():
        key_columns = {}
        for row in keys:
            if row["TABLE_NAME"] == f"dim_{name}" and row["REFERENCED_TABLE_NAME"] is None:
                key_columns.setdefault(row["CONSTRAINT_NAME"], []).append(row["COLUMN_NAME"])
        if [columns[0]] not in key_columns.values():
            raise ValueError(f"dim_{name} needs a unique constraint on {columns[0]}.")
    actual_foreign_keys = {
        (row["COLUMN_NAME"], row["REFERENCED_TABLE_NAME"], row["REFERENCED_COLUMN_NAME"])
        for row in keys
        if row["TABLE_NAME"] == "fact_order_items" and row["REFERENCED_TABLE_SCHEMA"] == database
    }
    if actual_foreign_keys != FOREIGN_KEYS:
        raise ValueError("fact_order_items has unexpected foreign keys.")


def insert_rows(cursor, table, columns, rows):
    placeholders = ", ".join(["%s"] * len(columns))
    statement = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"
    for start in range(0, len(rows), BATCH_SIZE):
        cursor.executemany(statement, rows[start:start + BATCH_SIZE])


def load_rows(cursor, dimensions, orders, items):
    for table in PRIMARY_KEYS:
        cursor.execute(f"SELECT 1 AS present FROM {table} LIMIT 1")
        if cursor.fetchone():
            raise ValueError(f"{table} already contains rows. Use --verify to check the existing load.")

    for table, (columns, rows) in dimensions.items():
        insert_rows(cursor, table, columns, rows)

    lookup = {}
    for name, singular in (("customers", "customer"), ("products", "product"), ("sellers", "seller")):
        cursor.execute(f"SELECT {singular}_id AS source_id, {singular}_key AS dimension_key FROM dim_{name}")
        lookup[name] = {row["source_id"]: row["dimension_key"] for row in cursor.fetchall()}

    facts = []
    for order_id, position, product_id, seller_id, price, freight in items:
        customer_id, purchase_date, status = orders[order_id]
        facts.append((
            order_id, position, lookup["customers"][customer_id], lookup["products"][product_id],
            lookup["sellers"][seller_id], purchase_date, status, price, freight,
        ))
    insert_rows(cursor, "fact_order_items", FACT_COLUMNS, facts)


def verify_rows(cursor, expected):
    query = (ROOT / "sql" / "validate_load.sql").read_text(encoding="utf-8")
    cursor.execute(query)
    actual = cursor.fetchone()
    mismatches = [name for name, value in expected.items() if actual.get(name) != value]
    if mismatches:
        raise ValueError("Loaded data does not match the cleaned CSVs for: " + ", ".join(mismatches))
    return actual


def run_database(connection, database, prepared, *, verify_only):
    dimensions, orders, items, expected = prepared
    with connection.cursor(dictionary=True) as cursor:
        cursor.execute("SELECT VERSION() AS version")
        version = cursor.fetchone()["version"]
        if not version.startswith("8.") or "mariadb" in version.lower():
            raise ValueError("This project expects a MySQL 8 server.")

        if not verify_only:
            cursor.execute("SET SESSION foreign_key_checks = 1")
            create_schema(cursor, database)
        verify_schema(cursor, database)
        if verify_only:
            return version, verify_rows(cursor, expected)

        # DDL commits separately. The dimension and fact inserts form one transaction.
        connection.commit()
        connection.start_transaction()
        try:
            load_rows(cursor, dimensions, orders, items)
            actual = verify_rows(cursor, expected)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        return version, actual


def update_report(version, expected, actual):
    heading = "## Load results"
    base, _, _ = REPORT_PATH.read_text(encoding="utf-8").partition(heading)
    table = markdown_table(
        ["Check", "Expected from CSVs", "Verified in MySQL"],
        ((name.replace("_", " "), f"{value:,}", f"{actual[name]:,}") for name, value in expected.items()),
    )
    text = f"{base}{heading}\n\nVerified on MySQL {version}. All checks passed.\n\n{table}\n"
    REPORT_PATH.write_text(text, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true", help="Check an existing load without inserting rows.")
    args = parser.parse_args()
    try:
        database, settings = mysql_settings()
        frames = load_datasets(ROOT / "data" / "processed", dtype=str, keep_default_na=False)
        prepared = prepare_data(frames)
        if args.verify:
            settings["database"] = database
        with connect_to_mysql(**settings) as connection:
            version, actual = run_database(connection, database, prepared, verify_only=args.verify)
    except Error as error:
        advice = {
            1044: "The MySQL account needs access to the project database.",
            1045: "Check the local MySQL username and password in .env.",
            1049: "The project database does not exist. Run the loader first.",
            2003: "Check the MySQL service and the host and port in .env.",
        }
        raise SystemExit(f"MySQL error {error.errno}. {advice.get(error.errno, 'Check the server and target schema.')}")
    except (ValueError, KeyError, OSError) as error:
        raise SystemExit(f"Warehouse load stopped: {error}") from error

    print(f"Verified {actual['fact_order_items']:,} item rows and {actual['qualifying_orders']:,} qualifying orders.")
    try:
        update_report(version, prepared[3], actual)
    except OSError:
        raise SystemExit("Database verification passed. Run --verify again to update the report.") from None
    print(f"Report saved to {REPORT_PATH}")


if __name__ == "__main__":
    main()

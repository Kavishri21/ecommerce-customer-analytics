"""Standardize and validate the Olist tables without discarding business records."""

from decimal import Decimal

import pandas as pd

from src.ingestion.explore_dataset import DATASETS, RELATIONSHIPS


TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"
ORDER_TIMESTAMPS = (
    "order_purchase_timestamp",
    "order_approved_at",
    "order_delivered_carrier_date",
    "order_delivered_customer_date",
    "order_estimated_delivery_date",
)
ORDER_STATUSES = {
    "approved", "canceled", "created", "delivered",
    "invoiced", "processing", "shipped", "unavailable",
}
PRODUCT_INTEGER_COLUMNS = (
    "product_name_lenght", "product_description_lenght", "product_photos_qty",
    "product_weight_g", "product_length_cm", "product_height_cm", "product_width_cm",
)


def require_no_rows(mask, problem):
    count = int(mask.sum())
    if count:
        raise ValueError(f"{problem} ({count:,} rows)")


def validate_keys(tables):
    for name, (_, _, key) in DATASETS.items():
        values = tables[name][key]
        require_no_rows(values.isna().any(axis=1), f"{name}: missing candidate key")
        require_no_rows(values.duplicated(keep=False), f"{name}: repeated candidate key")
    for child, column, parent in RELATIONSHIPS:
        if parent == "category_translations":
            continue  # Translation coverage is optional and reported on products.
        require_no_rows(
            ~tables[child][column].isin(tables[parent][column]),
            f"{child}.{column}: missing or absent from {parent}",
        )


def normalize_source(raw):
    tables = {}
    trimmed = {}
    for name, frame in raw.items():
        normalized = frame.apply(lambda column: column.str.strip())
        trimmed[name] = int((frame.notna() & normalized.ne(frame)).sum().sum())
        tables[name] = normalized.replace("", pd.NA)
    return tables, trimmed


def clean_timestamps(frame, table, columns):
    for column in columns:
        source = frame[column]
        parsed = pd.to_datetime(source, format=TIMESTAMP_FORMAT, errors="coerce")
        require_no_rows(source.notna() & parsed.isna(), f"{table}.{column}: invalid timestamp")
        frame[column] = parsed


def clean_integers(frame, columns, *, minimum=0):
    for column in columns:
        source = frame[column]
        valid = source.str.fullmatch(r"[0-9]+(?:\.0+)?", na=False)
        require_no_rows(source.notna() & ~valid, f"{column}: expected a whole number")
        values = source.str.replace(r"\.0+$", "", regex=True).astype("Int64")
        require_no_rows(values.lt(minimum), f"{column}: below minimum of {minimum}")
        frame[column] = values


def add_order_quality_fields(orders, items):
    purchase, approval, handoff, delivery, estimate = (orders[column] for column in ORDER_TIMESTAMPS)
    delivered = orders["order_status"].eq("delivered")
    orders["has_order_items"] = orders["order_id"].isin(items["order_id"])
    orders["is_qualifying_purchase"] = delivered & orders["has_order_items"]
    orders["has_chronology_conflict"] = (
        approval.lt(purchase) | handoff.lt(purchase) | handoff.lt(approval)
        | delivery.lt(purchase) | delivery.lt(approval) | delivery.lt(handoff)
        | estimate.dt.normalize().lt(purchase.dt.normalize())
    )
    orders["has_fulfillment_status_gap"] = (
        (delivered & (approval.isna() | handoff.isna() | delivery.isna()))
        | (orders["order_status"].eq("canceled") & delivery.notna())
    )

    orders_by_id = orders.set_index("order_id")
    item_purchase = items["order_id"].map(orders_by_id[ORDER_TIMESTAMPS[0]])
    item_approval = items["order_id"].map(orders_by_id[ORDER_TIMESTAMPS[1]])
    deadline = items["shipping_limit_date"]
    items["shipping_limit_needs_review"] = (
        deadline.lt(item_purchase) | deadline.lt(item_approval)
        | (deadline - item_purchase).gt(pd.Timedelta(days=365))
    )


def add_product_categories(products, translations):
    labels = translations.set_index("product_category_name")["product_category_name_english"]
    category = products["product_category_name"]
    english = category.map(labels)
    products["product_category_name_english"] = english
    status = pd.Series("translated", index=products.index, dtype="string")
    status = status.mask(english.isna(), "translation_missing")
    products["category_translation_status"] = status.mask(category.isna(), "missing_category")


def clean_datasets(raw):
    tables, trimmed = normalize_source(raw)
    orders = tables["orders"]
    items = tables["order_items"]
    products = tables["products"]

    id_fields = {
        "customers": ("customer_id", "customer_unique_id"),
        "orders": ("order_id", "customer_id"),
        "order_items": ("order_id", "product_id", "seller_id"),
        "products": ("product_id",),
        "sellers": ("seller_id",),
    }
    for name, columns in id_fields.items():
        for column in columns:
            valid = tables[name][column].str.fullmatch(r"[0-9a-f]{32}", na=False)
            require_no_rows(~valid, f"{name}.{column}: expected a 32-character Olist identifier")

    for name, column in (
        ("customers", "customer_zip_code_prefix"), ("sellers", "seller_zip_code_prefix"),
    ):
        values = tables[name][column]
        valid = values.str.fullmatch(r"[0-9]{1,5}", na=False)
        require_no_rows(values.notna() & ~valid, f"{name}.{column}: invalid ZIP prefix")
        tables[name][column] = values.str.zfill(5)

    require_no_rows(~orders["order_status"].isin(ORDER_STATUSES), "orders: missing or unknown status")
    clean_timestamps(orders, "orders", ORDER_TIMESTAMPS)
    clean_timestamps(items, "order_items", ("shipping_limit_date",))
    require_no_rows(orders[ORDER_TIMESTAMPS[0]].isna(), "orders: missing purchase timestamp")

    clean_integers(items, ("order_item_id",), minimum=1)
    clean_integers(products, PRODUCT_INTEGER_COLUMNS)
    validate_keys(tables)
    for column in ("price", "freight_value"):
        valid = items[column].str.fullmatch(r"[0-9]+(?:\.[0-9]{1,2})?", na=False)
        require_no_rows(~valid, f"order_items.{column}: expected a nonnegative amount with up to two decimal places")
        items[column] = items[column].map(lambda value: f"{Decimal(value):.2f}")
    add_order_quality_fields(orders, items)
    add_product_categories(products, tables["category_translations"])
    return tables, trimmed

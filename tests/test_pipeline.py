"""Small tests for the cleaning and analysis rules, with no database required."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import pandas as pd

from src.analysis.cohort_retention import calculate_cohorts
from src.analysis.rfm import calculate_rfm
from src.processing.cleaning import PRODUCT_INTEGER_COLUMNS, clean_datasets


def raw_fixture():
    customer, order, product, seller, identity = (letter * 32 for letter in "abcde")
    rows = {
        "customers": {"customer_id": customer, "customer_unique_id": identity,
                      "customer_zip_code_prefix": "00123"},
        "orders": {"order_id": order, "customer_id": customer, "order_status": "delivered",
                   "order_purchase_timestamp": "2018-01-02 10:00:00",
                   "order_approved_at": "2018-01-02 11:00:00",
                   "order_delivered_carrier_date": "2018-01-01 12:00:00",
                   "order_delivered_customer_date": "", "order_estimated_delivery_date": ""},
        "order_items": {"order_id": order, "order_item_id": "01", "product_id": product,
                        "seller_id": seller, "shipping_limit_date": "2018-01-03 12:00:00",
                        "price": "5.1", "freight_value": "0"},
        "products": {"product_id": product, "product_category_name": "",
                     **dict.fromkeys(PRODUCT_INTEGER_COLUMNS, "")},
        "sellers": {"seller_id": seller, "seller_zip_code_prefix": "04567"},
        "category_translations": {"product_category_name": "livros",
                                  "product_category_name_english": "books"},
    }
    return {name: pd.DataFrame([row], dtype="string") for name, row in rows.items()}


class CleaningTests(unittest.TestCase):
    def test_keeps_valid_records_and_flags_bad_chronology(self):
        tables, _ = clean_datasets(raw_fixture())
        self.assertEqual(tables["customers"].at[0, "customer_zip_code_prefix"], "00123")
        self.assertEqual(tables["order_items"].at[0, "freight_value"], "0.00")
        self.assertEqual(tables["products"].at[0, "category_translation_status"], "missing_category")
        self.assertTrue(tables["orders"].at[0, "has_chronology_conflict"])
        self.assertTrue(tables["orders"].at[0, "is_qualifying_purchase"])

    def test_rejects_orphan_references_and_invalid_prices(self):
        for column, value, message in (
            ("seller_id", "f" * 32, "absent from sellers"),
            ("price", "-2.00", "nonnegative amount"),
        ):
            with self.subTest(column=column):
                raw = raw_fixture()
                raw["order_items"].at[0, column] = value
                with self.assertRaisesRegex(ValueError, message):
                    clean_datasets(raw)

    def test_rejects_duplicate_item_numbers_after_parsing(self):
        raw = raw_fixture()
        items = raw["order_items"]
        raw["order_items"] = pd.concat([items, items.assign(order_item_id="1")], ignore_index=True)
        with self.assertRaisesRegex(ValueError, "repeated candidate key"):
            clean_datasets(raw)


class AnalysisTests(unittest.TestCase):
    def test_rfm_counts_one_order_with_two_items_once(self):
        orders = pd.DataFrame({
            "order_id": ["one", "two", "three"],
            "customer_unique_id": ["alice", "alice", "bob"],
            "purchase_date": pd.to_datetime(["2018-01-01", "2018-02-01", "2018-02-01"]),
        })
        with TemporaryDirectory() as scratch:
            item_path = Path(scratch) / "olist_order_items_dataset.csv"
            item_path.write_text(
                "order_id,price\none,15.10\none,14.90\ntwo,100.00\nthree,60.00\n",
                encoding="utf-8",
            )
            rows, reference = calculate_rfm(orders, Path(scratch))
        scores = rows.set_index("customer_unique_id")
        self.assertEqual(reference.date().isoformat(), "2018-02-02")
        self.assertEqual(scores.at["alice", "frequency"], 2)
        self.assertEqual(scores.at["alice", "monetary_cents"], 13000)
        self.assertEqual(scores.at["alice", "segment"], "Champions")
        self.assertEqual(scores.at["bob", "m_score"], 2)
        self.assertEqual(scores.at["bob", "segment"], "Potential Loyalists")

    def test_cohort_observed_zero_and_unobserved_blank(self):
        orders = pd.DataFrame(
            [
                ("early", "2020-01-15"), ("early", "2020-03-01"),
                ("repeat", "2020-02-02"), ("repeat", "2020-02-16"), ("repeat", "2020-04-01"),
                ("latest", "2020-04-25"), ("partial", "2020-05-10"),
            ],
            columns=["customer_unique_id", "purchase_date"],
        )
        orders["purchase_date"] = pd.to_datetime(orders["purchase_date"])
        counts, coverage = calculate_cohorts(orders)
        self.assertEqual(counts.loc["2020-02"].tolist(), [1, 0, 1])
        self.assertTrue(pd.isna(counts.at[pd.Period("2020-04", freq="M"), 1]))
        self.assertEqual(coverage["early_customers"], 1)
        self.assertEqual(coverage["late_customers"], 1)

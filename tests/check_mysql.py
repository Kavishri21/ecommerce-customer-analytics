"""Opt-in checks for the loaded warehouse and the four analytical queries."""

from collections import Counter, defaultdict
from decimal import Decimal
import unittest

from mysql.connector import Error

from src.ingestion.explore_dataset import ROOT, load_datasets
from src.warehouse.connection import connect_to_mysql, mysql_settings
from src.warehouse.load_warehouse import prepare_data, run_database


class MySQLChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        database, settings = mysql_settings()
        frames = load_datasets(ROOT / "data" / "processed", dtype=str, keep_default_na=False)
        cls.prepared = prepare_data(frames)
        cls.results = {}
        try:
            with connect_to_mysql(database=database, **settings) as connection:
                connection.start_transaction(readonly=True)
                cls.version, cls.loaded = run_database(
                    connection, database, cls.prepared, verify_only=True
                )
                with connection.cursor(dictionary=True) as cursor:
                    for name in ("monthly_sales", "repeat_customers", "product_categories", "top_sellers"):
                        query = ROOT / "sql" / "analytics" / f"{name}.sql"
                        cursor.execute(query.read_text(encoding="utf-8"))
                        cls.results[name] = cursor.fetchall()
                connection.rollback()
        except Error as error:
            raise RuntimeError(f"MySQL check failed (error {error.errno}).") from None

    def test_warehouse_matches_processed_files(self):
        self.assertEqual(self.loaded, self.prepared[3])

    def test_monthly_sales_and_repeat_frequencies(self):
        dimensions, orders, items, expected = self.prepared
        customer_identity = {row[0]: row[1] for row in dimensions["dim_customers"][1]}
        monthly_orders = defaultdict(set)
        monthly_value, monthly_freight = defaultdict(Decimal), defaultdict(Decimal)
        customer_orders = defaultdict(set)
        for order_id, _, _, _, price, freight in items:
            customer_id, day, status = orders[order_id]
            if status != "delivered":
                continue
            month = f"{day:%Y-%m}"
            monthly_orders[month].add(order_id)
            monthly_value[month] += price
            monthly_freight[month] += freight
            customer_orders[customer_identity[customer_id]].add(order_id)

        month_rows = self.results["monthly_sales"]
        expected_months = sorted({f"{row[0]:%Y-%m}" for row in dimensions["dim_date"][1]})
        self.assertEqual([row["purchase_month"] for row in month_rows], expected_months)
        previous = None
        for row in month_rows:
            month = row["purchase_month"]
            self.assertEqual(row["orders"], len(monthly_orders[month]))
            self.assertEqual(row["merchandise_value"], monthly_value[month])
            self.assertEqual(row["freight_value"], monthly_freight[month])
            self.assertEqual(row["previous_month_merchandise_value"], previous)
            previous = monthly_value[month]
        self.assertEqual(sum(row["orders"] for row in month_rows), expected["qualifying_orders"])

        frequencies = Counter(len(orders) for orders in customer_orders.values() if len(orders) >= 2)
        self.assertEqual(
            {row["orders_per_customer"]: row["customers"] for row in self.results["repeat_customers"]},
            frequencies,
        )

    def test_category_totals_and_seller_rankings(self):
        _, orders, items, expected = self.prepared
        qualifying_items = [item for item in items if orders[item[0]][2] == "delivered"]
        categories = self.results["product_categories"]
        self.assertEqual(sum(row["items"] for row in categories), expected["qualifying_items"])
        self.assertEqual(sum(row["merchandise_value"] for row in categories),
                         sum(item[4] for item in qualifying_items))

        seller_total = defaultdict(Decimal)
        for _, _, _, seller, price, _ in qualifying_items:
            seller_total[seller] += price
        ranking = sorted(seller_total.items(), key=lambda pair: (-pair[1], pair[0]))[:10]
        self.assertEqual(
            [(row["seller_id"], row["merchandise_value"]) for row in self.results["top_sellers"]],
            ranking,
        )

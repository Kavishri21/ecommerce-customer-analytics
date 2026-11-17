# E-commerce Customer Analytics: RFM Segmentation & Cohort Retention

An end-to-end data engineering project using the Olist Brazilian E-Commerce Public Dataset. Python and Pandas validate and clean six CSVs, MySQL stores an order-item warehouse, SQL answers sales questions, and Matplotlib shows customer segments and retention.

## Results

- The MySQL fact table contains **112,650 order items**, with zero items missing a dimension match. [Warehouse design](docs/data_warehouse_design.md) · [Load results](docs/data_loading_report.md)
- **96,478 qualifying orders** from **93,358 customers** generated **13,221,498.11** in merchandise value, excluding freight. [SQL analysis](docs/sql_analysis.md) · [RFM segmentation](docs/rfm_analysis.md)
- **390 of 81,264 customers (0.48%)** purchased again in the next calendar month among cohorts with a fully observed Month 1. [Cohort analysis](docs/cohort_analysis.md)

Start with the [business insights report](docs/business_insights.md) for the three charts and their interpretation.

## How the pipeline works

1. **Explore and clean.** Check the raw CSVs, standardize types, keep valid orders, and flag dates that need review. [Exploration](docs/dataset_exploration.md) · [Quality assessment](docs/data_quality_assessment.md) · [Cleaning rules](docs/data_cleaning_report.md)
2. **Load and query.** Load four dimensions for customers, products, sellers, and dates. Each row in the fact table represents one order item. Use `COUNT(DISTINCT order_id)` for order counts because an order can contain several items.
3. **Analyze customers.** A qualifying purchase is a delivered order with at least one item. Use `customer_unique_id` across purchases. RFM groups customers by days since purchase, order frequency, and merchandise spend. Cohort retention measures the share of a first-purchase group that buys in each later month.

## Reproduce on Windows

Use Python 3.11.5 and PowerShell from the project root. The warehouse steps also need local MySQL 8. In VS Code, select `.venv\Scripts\python.exe` as the interpreter and as the kernel if you use Jupyter.

### 1. Set up Python and the source data

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
New-Item -ItemType Directory -Force .\data\raw | Out-Null
```

If pip reports a Windows path-length error, use a shorter project path before creating `.venv`.

Download the [Olist dataset on Kaggle](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) and extract these six files into `data/raw/`.

- `olist_customers_dataset.csv`
- `olist_orders_dataset.csv`
- `olist_order_items_dataset.csv`
- `olist_products_dataset.csv`
- `olist_sellers_dataset.csv`
- `product_category_name_translation.csv`

### 2. Run the local CSV pipeline

These commands work with the CSVs and run without MySQL.

```powershell
.\.venv\Scripts\python.exe -B .\src\ingestion\explore_dataset.py
.\.venv\Scripts\python.exe -B .\src\ingestion\assess_data_quality.py
.\.venv\Scripts\python.exe -B -m src.processing.clean_dataset
.\.venv\Scripts\python.exe -B -m src.analysis.rfm
.\.venv\Scripts\python.exe -B -m src.analysis.cohort_retention
.\.venv\Scripts\python.exe -B -m src.analysis.visualize_results
```

Cleaned CSVs and customer and cohort results appear in `data/processed/`. Reports and charts appear in `docs/` and `docs/figures/`.

### 3. Load MySQL and run SQL

Create `.env` from `.env.example` if the file is absent. Set `DB_NAME` to a project-only database, such as `olist_analytics`. Enter your local MySQL username and password in the ignored `.env`.

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

After saving the configuration, run the loader. The MySQL account needs permission to create the project database and tables, define foreign keys, and read and insert rows.

```powershell
.\.venv\Scripts\python.exe -B -m src.warehouse.load_warehouse
```

Use `--verify` with that command to check an existing load. The normal load expects empty warehouse tables. To inspect the SQL analysis, select `DB_NAME` in your SQL client and execute the files in [sql/analytics](sql/analytics/).

## Run the tests

```powershell
# Local tests use small examples and need only the Python dependencies.
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -p test_pipeline.py -v

# Live checks require a loaded MySQL warehouse and run in a read-only transaction.
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -p check_mysql.py -v
```

The [local tests](tests/test_pipeline.py) cover cleaning rules, distinct order counts in RFM, and the difference between zero and blank cohort cells. The [MySQL checks](tests/check_mysql.py) verify the warehouse keys and totals, then compare the four analytical queries with the cleaned CSVs.

The local pipeline was replayed in a fresh Python 3.11.5 environment. Starting with the six raw CSVs, it regenerated nine byte-for-byte matching CSVs and rendered all three charts. The warehouse checks passed on MySQL 8.0.42.

The repository keeps Python modules in `src/`, SQL in `sql/`, tests in `tests/`, and documentation in `docs/`. The local datasets, credentials, and Python environment are ignored by Git.

# Olist MySQL data loading

The loader reads the six cleaned CSVs and loads the [five-table star schema](data_warehouse_design.md). MySQL generates keys for the customer, product, and seller dimensions. The loader looks up those keys when it builds each item row.

## Run locally

1. Open the project's ignored `.env` file. Enter your local MySQL username in `DB_USER` and password in `DB_PASSWORD`. Set `DB_NAME` to the project database. The prepared file uses `olist_analytics` on `localhost:3306`.
2. Use an account that can create the project database and tables, define the foreign keys, and read and insert rows in that database.
3. From the project root in PowerShell, run the loader.

   ```powershell
   .\.venv\Scripts\python.exe -B -m src.warehouse.load_warehouse
   ```

   The loader creates the database and tables if needed. It loads the four dimensions first, then the item fact table. The inserts share one transaction, so a failed insert or validation rolls them all back. The schema can remain after a failed load because MySQL commits schema changes separately. [MySQL transaction behavior for DDL](https://dev.mysql.com/doc/refman/8.0/en/implicit-commit.html)

4. To check an existing load, use the verification command. The regular load command stops if any target table already contains rows.

   ```powershell
   .\.venv\Scripts\python.exe -B -m src.warehouse.load_warehouse --verify
   ```

## What the checks cover

- Confirm that the five tables use InnoDB and have the expected primary keys and dimension relationships.
- Compare table counts, distinct order counts, delivered order and item counts, and exact merchandise and freight totals with the cleaned CSVs.
- Run [validate_load.sql](../sql/validate_load.sql) in the selected project database to view the SQL checks directly. The query counts item rows with missing dimension matches.
- An offline two-item test covered the load order, validation query, protection against loading twice, and rollback on a duplicate item. The live MySQL check is recorded below.

## Load results

Verified on MySQL 8.0.42. All checks passed.

| Check | Expected from CSVs | Verified in MySQL |
| --- | --- | --- |
| dim customers | 99,441 | 99,441 |
| dim products | 32,951 | 32,951 |
| dim sellers | 3,095 | 3,095 |
| dim date | 774 | 774 |
| fact order items | 112,650 | 112,650 |
| orders with items | 98,666 | 98,666 |
| qualifying orders | 96,478 | 96,478 |
| qualifying items | 110,197 | 110,197 |
| merchandise total | 13,591,643.70 | 13,591,643.70 |
| freight total | 2,251,909.54 | 2,251,909.54 |
| items missing a dimension | 0 | 0 |

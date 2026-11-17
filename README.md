# E-commerce Customer Analytics: RFM Segmentation & Cohort Retention

This project will use e-commerce transaction data to segment customers by recency, frequency, and monetary value (RFM) and measure retention across purchase cohorts. The project is at the environment setup stage.

## Project layout

```text
data/
  raw/         Source datasets
  processed/   Cleaned data and analysis outputs
notebooks/     Jupyter notebooks for exploration and analysis
sql/           MySQL queries and scripts
src/           Reusable Python modules
```

## Local setup

Use Windows PowerShell from the project root. Install Python 3.11, VS Code with the Python and Jupyter extensions, and a local MySQL 8 server. Git is used for version control.

1. Create the virtual environment and install the dependencies if setting up a fresh copy.

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

2. In VS Code, run **Python: Select Interpreter** and select `.venv\Scripts\python.exe`. Select the same environment as the kernel when opening a notebook. To launch Jupyter Notebook from PowerShell, run:

   ```powershell
   .\.venv\Scripts\python.exe -m notebook
   ```

3. When database work begins, use the template to create `.env` if it does not already exist. Set the database name and MySQL account credentials in `.env`.

   ```powershell
   Copy-Item .env.example .env
   ```

   The host and port default to `localhost` and `3306`. Keep credentials in the ignored `.env` file.

4. Check the environment.

   ```powershell
   .\.venv\Scripts\python.exe --version
   .\.venv\Scripts\python.exe -m pip check
   ```

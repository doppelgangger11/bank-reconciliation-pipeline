import os

import pandas as pd
import psycopg2
from dotenv import load_dotenv


# --------------------------------------------------
# Configuration
# --------------------------------------------------

load_dotenv()

DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT"),
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
}


# --------------------------------------------------
# Read data
# --------------------------------------------------

def read_clean_data():
    """
    Reads the same clean.* tables that reconcile.py uses,
    so quality checks reflect what actually gets reconciled.
    """

    connection = psycopg2.connect(**DB_CONFIG)

    try:
        bank = pd.read_sql(
            """
            SELECT
                id, transaction_id, account_id,
                amount, currency, transaction_date
            FROM clean.bank_transactions_clean
            """,
            connection,
        )

        ledger = pd.read_sql(
            """
            SELECT
                id, record_id, account_id,
                amount, currency, record_date
            FROM clean.ledger_records_clean
            """,
            connection,
        )
    finally:
        connection.close()

    return bank, ledger


# --------------------------------------------------
# Individual checks
# --------------------------------------------------

def check_nulls(df: pd.DataFrame, columns: list[str], source_name: str):
    """
    Counts nulls per column. Returns a list of issue dicts,
    one row per column that actually has nulls (no noise for clean columns).
    """
    issues = []

    for col in columns:
        null_count = df[col].isna().sum()
        if null_count > 0:
            issues.append({
                "source": source_name,
                "check": "null_values",
                "column": col,
                "count": int(null_count),
                "detail": f"{null_count} missing values in '{col}'",
            })

    return issues


def check_duplicates(df: pd.DataFrame, key_columns: list[str], source_name: str):
    """
    Flags fully duplicated rows on the given key.
    This mirrors the logic reconcile.py already uses to find
    duplicates, so numbers here should match what ends up
    tagged as 'duplicate' in the reconciliation report.
    """
    duplicate_mask = df.duplicated(subset=key_columns, keep=False)
    count = int(duplicate_mask.sum())

    if count == 0:
        return []

    return [{
        "source": source_name,
        "check": "duplicates",
        "column": ", ".join(key_columns),
        "count": count,
        "detail": f"{count} rows share the same {key_columns}",
    }]


def check_amount_range(df: pd.DataFrame, min_value: float, max_value: float, source_name: str):
    """
    Flags amounts outside a sane range (e.g. negative or absurdly large).
    Adjust min_value/max_value to whatever makes sense for your generated data.
    """
    out_of_range = df[(df["amount"] < min_value) | (df["amount"] > max_value)]
    count = len(out_of_range)

    if count == 0:
        return []

    return [{
        "source": source_name,
        "check": "amount_range",
        "column": "amount",
        "count": count,
        "detail": f"{count} rows outside [{min_value}, {max_value}]",
    }]


def check_date_parseable(df: pd.DataFrame, date_column: str, source_name: str):
    """
    By the time data reaches clean.*, dates should already be real
    DATE/TIMESTAMP columns (parsed in clean.py). This check just confirms
    there are no NaT values left over from failed parsing there.
    """
    unparseable = df[date_column].isna().sum()

    if unparseable == 0:
        return []

    return [{
        "source": source_name,
        "check": "unparseable_dates",
        "column": date_column,
        "count": int(unparseable),
        "detail": f"{unparseable} rows have an invalid/missing {date_column}",
    }]


# --------------------------------------------------
# Run all checks
# --------------------------------------------------

def run_all_checks(bank: pd.DataFrame, ledger: pd.DataFrame) -> pd.DataFrame:
    """
    Runs every check against both sources and returns one combined
    DataFrame. This is what report.py will read for the
    'Data Quality Issues' sheet.
    """

    issues = []

    issues += check_nulls(bank, ["account_id", "amount", "currency", "transaction_date"], "bank")
    issues += check_nulls(ledger, ["account_id", "amount", "currency", "record_date"], "ledger")

    issues += check_duplicates(bank, ["transaction_id", "account_id", "amount", "transaction_date"], "bank")
    issues += check_duplicates(ledger, ["record_id", "account_id", "amount", "record_date"], "ledger")

    # Adjust these bounds to whatever your generate_data.py actually produces
    issues += check_amount_range(bank, min_value=0, max_value=1_000_000, source_name="bank")
    issues += check_amount_range(ledger, min_value=0, max_value=1_000_000, source_name="ledger")

    issues += check_date_parseable(bank, "transaction_date", "bank")
    issues += check_date_parseable(ledger, "record_date", "ledger")

    return pd.DataFrame(issues)


# --------------------------------------------------
# Main
# --------------------------------------------------

def main():

    print("Reading clean data...")
    bank, ledger = read_clean_data()

    print("Running quality checks...")
    issues = run_all_checks(bank, ledger)

    if issues.empty:
        print("No data quality issues found.")
    else:
        print(f"Found {len(issues)} issue group(s):")
        print(issues)

    # Не возвращаем DataFrame — Airflow не умеет его сериализовать в XCom
    return None


if __name__ == "__main__":
    main()
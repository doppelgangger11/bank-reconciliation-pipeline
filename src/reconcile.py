import os
from decimal import Decimal

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

    connection = psycopg2.connect(
        **DB_CONFIG
    )

    try:

        bank = pd.read_sql(
            """
            SELECT
                id,
                transaction_id,
                account_id,
                amount,
                currency,
                transaction_date
            FROM clean.bank_transactions_clean
            """,
            connection,
        )

        ledger = pd.read_sql(
            """
            SELECT
                id,
                record_id,
                account_id,
                amount,
                currency,
                record_date
            FROM clean.ledger_records_clean
            """,
            connection,
        )

    finally:
        connection.close()

    bank["transaction_date"] = pd.to_datetime(
        bank["transaction_date"]
    )

    ledger["record_date"] = pd.to_datetime(
        ledger["record_date"]
    )

    return bank, ledger


# --------------------------------------------------
# Duplicates
# --------------------------------------------------

def find_duplicates(
    bank: pd.DataFrame,
    ledger: pd.DataFrame,
):

    bank_duplicates = set(
        bank.loc[
            bank.duplicated(
                subset=[
                    "transaction_id",
                    "account_id",
                    "amount",
                    "transaction_date",
                    "currency",
                ],
                keep=False,
            ),
            "id",
        ]
    )

    ledger_duplicates = set(
        ledger.loc[
            ledger.duplicated(
                subset=[
                    "record_id",
                    "account_id",
                    "amount",
                    "record_date",
                    "currency",
                ],
                keep=False,
            ),
            "id",
        ]
    )

    return bank_duplicates, ledger_duplicates


# --------------------------------------------------
# Reconciliation
# --------------------------------------------------

def reconcile(
    bank: pd.DataFrame,
    ledger: pd.DataFrame,
):

    results = []

    bank_duplicates, ledger_duplicates = (
        find_duplicates(
            bank,
            ledger,
        )
    )

    used_bank = set()
    used_ledger = set()

    # ----------------------------------------------
    # 1. Duplicate records
    # ----------------------------------------------

    for bank_id in bank_duplicates:

        row = bank[
            bank["id"] == bank_id
        ].iloc[0]

        results.append({
            "key": (
                f"{row['account_id']}_"
                f"{row['transaction_date'].date()}"
            ),
            "status": "duplicate",
            "amount_bank": row["amount"],
            "amount_ledger": None,
            "diff": None,
            "note": "Duplicate in bank",
        })

        used_bank.add(bank_id)

    for ledger_id in ledger_duplicates:

        row = ledger[
            ledger["id"] == ledger_id
        ].iloc[0]

        results.append({
            "key": (
                f"{row['account_id']}_"
                f"{row['record_date'].date()}"
            ),
            "status": "duplicate",
            "amount_bank": None,
            "amount_ledger": row["amount"],
            "diff": None,
            "note": "Duplicate in ledger",
        })

        used_ledger.add(ledger_id)

    # ----------------------------------------------
    # 2. Exact matches
    # ----------------------------------------------

    for bank_index, bank_row in bank.iterrows():

        bank_id = bank_row["id"]

        if bank_id in used_bank:
            continue

        candidates = ledger[
            (ledger["account_id"] == bank_row["account_id"])
            & (
                ledger["record_date"]
                == bank_row["transaction_date"]
            )
            & (
                ledger["amount"]
                == bank_row["amount"]
            )
            & (
                ledger["currency"]
                == bank_row["currency"]
            )
        ]

        candidates = candidates[
            ~candidates["id"].isin(used_ledger)
        ]

        if not candidates.empty:

            ledger_row = candidates.iloc[0]
            ledger_id = ledger_row["id"]

            results.append({
                "key": (
                    f"{bank_row['account_id']}_"
                    f"{bank_row['transaction_date'].date()}"
                ),
                "status": "matched",
                "amount_bank": bank_row["amount"],
                "amount_ledger": ledger_row["amount"],
                "diff": Decimal("0.00"),
                "note": "",
            })

            used_bank.add(bank_id)
            used_ledger.add(ledger_id)

    # ----------------------------------------------
    # 3. Mismatch
    #    account_id + date +/- 1 day
    # ----------------------------------------------

    for bank_index, bank_row in bank.iterrows():

        bank_id = bank_row["id"]

        if bank_id in used_bank:
            continue

        date_from = (
            bank_row["transaction_date"]
            - pd.Timedelta(days=1)
        )

        date_to = (
            bank_row["transaction_date"]
            + pd.Timedelta(days=1)
        )

        candidates = ledger[
            (ledger["account_id"] == bank_row["account_id"])
            & (
                ledger["record_date"] >= date_from
            )
            & (
                ledger["record_date"] <= date_to
            )
            & (
                ledger["currency"]
                == bank_row["currency"]
            )
        ]

        candidates = candidates[
            ~candidates["id"].isin(used_ledger)
        ]

        if not candidates.empty:

            ledger_row = candidates.iloc[0]
            ledger_id = ledger_row["id"]

            diff = (
                bank_row["amount"]
                - ledger_row["amount"]
            )

            results.append({
                "key": (
                    f"{bank_row['account_id']}_"
                    f"{bank_row['transaction_date'].date()}"
                ),
                "status": "mismatch",
                "amount_bank": bank_row["amount"],
                "amount_ledger": ledger_row["amount"],
                "diff": diff,
                "note": "Amount differs",
            })

            used_bank.add(bank_id)
            used_ledger.add(ledger_id)

    # ----------------------------------------------
    # 4. Missing in ledger
    # ----------------------------------------------

    for _, bank_row in bank.iterrows():

        bank_id = bank_row["id"]

        if bank_id in used_bank:
            continue

        results.append({
            "key": (
                f"{bank_row['account_id']}_"
                f"{bank_row['transaction_date'].date()}"
            ),
            "status": "missing_in_ledger",
            "amount_bank": bank_row["amount"],
            "amount_ledger": None,
            "diff": None,
            "note": "Transaction exists only in bank",
        })

    # ----------------------------------------------
    # 5. Missing in bank
    # ----------------------------------------------

    for _, ledger_row in ledger.iterrows():

        ledger_id = ledger_row["id"]

        if ledger_id in used_ledger:
            continue

        results.append({
            "key": (
                f"{ledger_row['account_id']}_"
                f"{ledger_row['record_date'].date()}"
            ),
            "status": "missing_in_bank",
            "amount_bank": None,
            "amount_ledger": ledger_row["amount"],
            "diff": None,
            "note": "Transaction exists only in ledger",
        })

    return pd.DataFrame(results)


# --------------------------------------------------
# Save results
# --------------------------------------------------


def to_pyfloat(value):
    if value is None or pd.isna(value):
        return None
    return float(value)


def save_results(
    results: pd.DataFrame,
) -> None:

    connection = psycopg2.connect(
        **DB_CONFIG
    )

    try:

        with connection.cursor() as cursor:

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS
                reports.reconciliation_results (
                    id SERIAL PRIMARY KEY,
                    key TEXT,
                    status TEXT,
                    amount_bank NUMERIC(14, 2),
                    amount_ledger NUMERIC(14, 2),
                    diff NUMERIC(14, 2),
                    note TEXT
                )
            """)

            cursor.execute(
                """
                TRUNCATE TABLE
                reports.reconciliation_results
                """
            )

            for _, row in results.iterrows():

                cursor.execute(
                    """
                    INSERT INTO
                    reports.reconciliation_results (
                        key,
                        status,
                        amount_bank,
                        amount_ledger,
                        diff,
                        note
                    )
                    VALUES (
                        %s, %s, %s, %s, %s, %s
                    )
                    """,
                    (
                        row["key"],
                        row["status"],
                        to_pyfloat(row["amount_bank"]),
                        to_pyfloat(row["amount_ledger"]),
                        to_pyfloat(row["diff"]),
                        row["note"],
                    ),
                )

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


# --------------------------------------------------
# Main
# --------------------------------------------------

def main():

    print("Reading clean data...")

    bank, ledger = read_clean_data()

    print(f"Bank rows:   {len(bank)}")
    print(f"Ledger rows: {len(ledger)}")

    print("Running reconciliation...")

    results = reconcile(
        bank,
        ledger,
    )

    save_results(results)

    print()
    print("Reconciliation completed.")
    print()
    print(results["status"].value_counts())


if __name__ == "__main__":
    main()
from pathlib import Path
import csv
import json
import os

import psycopg2
from dotenv import load_dotenv


# --------------------------------------------------
# Configuration
# --------------------------------------------------

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT"),
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
}


# --------------------------------------------------
# CSV
# --------------------------------------------------

def read_csv(filename: str) -> list[dict]:
    path = DATA_DIR / filename

    with path.open(
        "r",
        newline="",
        encoding="utf-8",
    ) as file:
        reader = csv.DictReader(file)
        return list(reader)


# --------------------------------------------------
# PostgreSQL
# --------------------------------------------------

def load_ledger(
    cursor,
    rows: list[dict],
) -> None:

    query = """
        INSERT INTO staging.ledger_records (
            record_id,
            account_id,
            amount,
            currency,
            record_date,
            raw_row
        )
        VALUES (%s, %s, %s, %s, %s, %s)
    """

    for row in rows:
        cursor.execute(
            query,
            (
                row["transaction_id"],
                row["account_id"],
                row["amount"],
                row["currency"],
                row["date"],
                json.dumps(row, ensure_ascii=False),
            ),
        )


def load_bank(
    cursor,
    rows: list[dict],
) -> None:

    query = """
        INSERT INTO staging.bank_transactions (
            transaction_id,
            account_id,
            amount,
            currency,
            transaction_date,
            raw_row
        )
        VALUES (%s, %s, %s, %s, %s, %s)
    """

    for row in rows:
        cursor.execute(
            query,
            (
                row["transaction_id"],
                row["account_id"],
                row["amount"],
                row["currency"],
                row["date"],
                json.dumps(row, ensure_ascii=False),
            ),
        )


# --------------------------------------------------
# Main
# --------------------------------------------------

def main():

    print("Reading CSV files...")

    ledger_rows = read_csv("ledger_records.csv")
    bank_rows = read_csv("bank_transactions.csv")

    print(f"Ledger rows: {len(ledger_rows)}")
    print(f"Bank rows:   {len(bank_rows)}")

    print("Connecting to PostgreSQL...")

    connection = psycopg2.connect(**DB_CONFIG)

    try:

        with connection.cursor() as cursor:

            print("Truncating staging tables...")

            cursor.execute("TRUNCATE TABLE staging.ledger_records RESTART IDENTITY")
            cursor.execute("TRUNCATE TABLE staging.bank_transactions RESTART IDENTITY")

            print("Loading staging.ledger_records...")

            load_ledger(
                cursor,
                ledger_rows,
            )

            print("Loading staging.bank_transactions...")

            load_bank(
                cursor,
                bank_rows,
            )

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()

    print()
    print("Load completed.")


if __name__ == "__main__":
    main()
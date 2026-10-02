import os
from decimal import Decimal, InvalidOperation

import psycopg2
from datetime import datetime
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
# Parsing
# --------------------------------------------------

def parse_date(value: str):
    """
    Convert supported date formats to DATE-compatible value.
    """

    value = value.strip()

    for date_format in (
        "%Y-%m-%d",
        "%d.%m.%Y",
    ):
        try:
            return datetime.strptime(
                value,
                date_format,
            ).date()

        except ValueError:
            continue

    raise ValueError(
        f"Unsupported date format: {value}"
    )


def clean_amount(value: str) -> Decimal:
    """
    Convert amount to Decimal with 2 decimal places.
    """

    try:
        amount = Decimal(str(value))

    except InvalidOperation:
        raise ValueError(
            f"Invalid amount: {value}"
        )

    return amount.quantize(
        Decimal("0.01")
    )


# --------------------------------------------------
# Clean ledger
# --------------------------------------------------

def clean_ledger(
    cursor,
) -> None:

    cursor.execute("""
        SELECT
            record_id,
            account_id,
            amount,
            currency,
            record_date
        FROM staging.ledger_records
    """)

    rows = cursor.fetchall()

    for row in rows:

        record_id = row[0]
        account_id = row[1]
        amount = clean_amount(row[2])
        currency = row[3]
        record_date = parse_date(row[4])

        cursor.execute(
            """
            INSERT INTO clean.ledger_records_clean (
                record_id,
                account_id,
                amount,
                currency,
                record_date
            )
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                record_id,
                account_id,
                amount,
                currency,
                record_date,
            ),
        )


# --------------------------------------------------
# Clean bank
# --------------------------------------------------

def clean_bank(
    cursor,
) -> None:

    cursor.execute("""
        SELECT
            transaction_id,
            account_id,
            amount,
            currency,
            transaction_date
        FROM staging.bank_transactions
    """)

    rows = cursor.fetchall()

    for row in rows:

        transaction_id = row[0]
        account_id = row[1]
        amount = clean_amount(row[2])
        currency = row[3]
        transaction_date = parse_date(row[4])

        cursor.execute(
            """
            INSERT INTO clean.bank_transactions_clean (
                transaction_id,
                account_id,
                amount,
                currency,
                transaction_date
            )
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                transaction_id,
                account_id,
                amount,
                currency,
                transaction_date,
            ),
        )


# --------------------------------------------------
# Main
# --------------------------------------------------

def main():

    print("Connecting to PostgreSQL...")

    connection = psycopg2.connect(
        **DB_CONFIG
    )

    try:

        with connection.cursor() as cursor:

            print(
                "Cleaning ledger_records..."
            )

            clean_ledger(cursor)

            print(
                "Cleaning bank_transactions..."
            )

            clean_bank(cursor)

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()

    print()
    print("Cleaning completed.")


if __name__ == "__main__":
    main()
from pathlib import Path

import csv
import random
from datetime import datetime

from faker import Faker


# --------------------------------------------------
# Configuration
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

DATA_DIR.mkdir(exist_ok=True)

RECORD_COUNT = 50_000

CURRENCIES = ["KZT", "USD", "EUR", "RUB"]

fake = Faker()


# --------------------------------------------------
# Data generation
# --------------------------------------------------

def generate_reference_data(count: int) -> list[dict]:
    """Generate clean reference transactions."""

    start_date = datetime(2025, 1, 1)
    end_date = datetime(2026, 9, 29)

    transactions = []

    for transaction_id in range(1, count + 1):

        date = fake.date_between(
            start_date=start_date,
            end_date=end_date,
        )

        transactions.append({
            "transaction_id": transaction_id,
            "account_id": random.randint(100_000, 999_999),
            "amount": round(
                random.uniform(100, 500_000),
                2,
            ),
            "date": date,
            "currency": random.choice(CURRENCIES),
        })

    return transactions


# --------------------------------------------------
# Bank corruption
# --------------------------------------------------

def corrupt_bank_data(
    reference_data: list[dict],
) -> list[dict]:

    bank_data = [
        row.copy()
        for row in reference_data
    ]

    total = len(bank_data)

    # ----------------------------------------------
    # 1. Amount mismatches — 2%
    # ----------------------------------------------

    mismatch_count = int(total * 0.02)

    mismatch_indexes = random.sample(
        range(total),
        mismatch_count,
    )

    for index in mismatch_indexes:

        amount = bank_data[index]["amount"]

        bank_data[index]["amount"] = round(
            amount + random.choice(
                [-0.01, 0.01, 0.05, -0.05]
            ),
            2,
        )

    # ----------------------------------------------
    # 2. Missing records — 1%
    # ----------------------------------------------

    missing_count = int(total * 0.01)

    missing_indexes = set(
        random.sample(
            range(total),
            missing_count,
        )
    )

    bank_data = [
        row
        for index, row in enumerate(bank_data)
        if index not in missing_indexes
    ]

    # ----------------------------------------------
    # 3. Duplicate records — 1%
    # ----------------------------------------------

    duplicate_count = int(total * 0.01)

    duplicates = random.sample(
        bank_data,
        duplicate_count,
    )

    bank_data.extend(
        row.copy()
        for row in duplicates
    )

    # ----------------------------------------------
    # 4. Date format changes — 5%
    # ----------------------------------------------

    date_count = int(len(bank_data) * 0.05)

    date_indexes = random.sample(
        range(len(bank_data)),
        date_count,
    )

    for index in date_indexes:

        date = bank_data[index]["date"]

        bank_data[index]["date"] = date.strftime(
            "%d.%m.%Y"
        )

    return bank_data


# --------------------------------------------------
# CSV
# --------------------------------------------------

def save_csv(
    filename: str,
    data: list[dict],
) -> None:

    path = DATA_DIR / filename

    fieldnames = [
        "transaction_id",
        "account_id",
        "amount",
        "date",
        "currency",
    ]

    with path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )

        writer.writeheader()
        writer.writerows(data)

    print(f"Saved: {path}")


# --------------------------------------------------
# Main
# --------------------------------------------------

def main():

    print("Generating reference data...")

    reference_data = generate_reference_data(
        RECORD_COUNT
    )

    print("Creating corrupted bank data...")

    bank_data = corrupt_bank_data(
        reference_data
    )

    save_csv(
        "ledger_records.csv",
        reference_data,
    )

    save_csv(
        "bank_transactions.csv",
        bank_data,
    )

    print()
    print("Done.")
    print(f"Ledger records: {len(reference_data)}")
    print(
        f"Bank transactions: {len(bank_data)}"
    )


if __name__ == "__main__":
    main()
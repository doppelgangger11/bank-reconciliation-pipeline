import pandas as pd
import sys

sys.path.append("../src")

from reconcile import reconcile # type: ignore


def test_exact_match_is_matched():
    """
    Identical account_id, amount, date, currency on both sides
    should be tagged as 'matched'.
    """

    bank = pd.DataFrame([
        {"id": 1, "transaction_id": "T1", "account_id": "ACC1", "amount": 100.0,
         "currency": "USD", "transaction_date": pd.Timestamp("2026-01-10")},
    ])

    ledger = pd.DataFrame([
        {"id": 1, "record_id": "R1", "account_id": "ACC1", "amount": 100.0,
         "currency": "USD", "record_date": pd.Timestamp("2026-01-10")},
    ])

    results = reconcile(bank, ledger)

    assert len(results) == 1
    assert results.iloc[0]["status"] == "matched"


def test_amount_difference_is_mismatch():
    """
    Same account and date, but different amount -> mismatch,
    with diff correctly calculated as bank - ledger.
    """

    bank = pd.DataFrame([
        {"id": 1, "transaction_id": "T1", "account_id": "ACC1", "amount": 150.0,
         "currency": "USD", "transaction_date": pd.Timestamp("2026-01-10")},
    ])

    ledger = pd.DataFrame([
        {"id": 1, "record_id": "R1", "account_id": "ACC1", "amount": 100.0,
         "currency": "USD", "record_date": pd.Timestamp("2026-01-10")},
    ])

    results = reconcile(bank, ledger)

    assert len(results) == 1
    assert results.iloc[0]["status"] == "mismatch"
    assert results.iloc[0]["diff"] == 50.0


def test_missing_in_ledger_is_flagged():
    """
    A bank transaction with no matching account_id in ledger at all
    should show up as missing_in_ledger, not silently disappear.
    """

    bank = pd.DataFrame([
        {"id": 1, "transaction_id": "T1", "account_id": "ACC1", "amount": 100.0,
         "currency": "USD", "transaction_date": pd.Timestamp("2026-01-10")},
    ])

    ledger = pd.DataFrame([
        {"id": 1, "record_id": "R1", "account_id": "ACC2", "amount": 100.0,
         "currency": "USD", "record_date": pd.Timestamp("2026-01-10")},
    ])

    results = reconcile(bank, ledger)

    statuses = set(results["status"])
    assert "missing_in_ledger" in statuses
    assert "missing_in_bank" in statuses
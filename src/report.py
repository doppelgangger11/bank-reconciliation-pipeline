import os

import pandas as pd
import psycopg2
from dotenv import load_dotenv

from quality_checks import read_clean_data, run_all_checks


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

OUTPUT_PATH = "reports/reconciliation_report.xlsx"


# --------------------------------------------------
# Read reconciliation results
# --------------------------------------------------

def read_reconciliation_results() -> pd.DataFrame:

    connection = psycopg2.connect(**DB_CONFIG)

    try:
        results = pd.read_sql(
            """
            SELECT key, status, amount_bank, amount_ledger, diff, note
            FROM reports.reconciliation_results
            """,
            connection,
        )
    finally:
        connection.close()

    return results


# --------------------------------------------------
# Build the summary sheet
# --------------------------------------------------

def build_summary(results: pd.DataFrame) -> pd.DataFrame:
    """
    One row per status, with counts and total discrepancy amount.
    This is the sheet a client/manager opens first, so keep it short.
    """

    summary = (
        results
        .groupby("status")
        .agg(
            count=("status", "size"),
            total_diff=("diff", lambda x: x.dropna().abs().sum()),
        )
        .reset_index()
    )

    total_records = len(results)
    summary["pct_of_total"] = (summary["count"] / total_records * 100).round(2)

    return summary


# --------------------------------------------------
# Write the Excel file
# --------------------------------------------------

def write_report(
    summary: pd.DataFrame,
    results: pd.DataFrame,
    issues: pd.DataFrame,
    output_path: str,
) -> None:

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    discrepancies = results[
        results["status"].isin(["mismatch", "missing_in_ledger", "missing_in_bank", "duplicate"])
    ]

    with pd.ExcelWriter(output_path, engine="xlsxwriter") as writer:

        summary.to_excel(writer, sheet_name="Summary", index=False)
        discrepancies.to_excel(writer, sheet_name="Discrepancies", index=False)

        if issues.empty:
            pd.DataFrame([{"info": "No data quality issues found."}]).to_excel(
                writer, sheet_name="Data Quality Issues", index=False
            )
        else:
            issues.to_excel(writer, sheet_name="Data Quality Issues", index=False)

        workbook = writer.book

        # ---- Conditional formatting: highlight mismatches red ----
        discrepancies_sheet = writer.sheets["Discrepancies"]

        red_format = workbook.add_format({
            "bg_color": "#FFC7CE",
            "font_color": "#9C0006",
        })

        if "status" in discrepancies.columns and len(discrepancies) > 0:
            status_col_index = discrepancies.columns.get_loc("status")

            discrepancies_sheet.conditional_format(
                1, 0, len(discrepancies), len(discrepancies.columns) - 1,
                {
                    "type": "formula",
                    "criteria": f'=${chr(65 + status_col_index)}2="mismatch"',
                    "format": red_format,
                },
            )

        # ---- Basic column width so it's readable without manual resizing ----
        for sheet_name, df in [
            ("Summary", summary),
            ("Discrepancies", discrepancies),
            ("Data Quality Issues", issues if not issues.empty else pd.DataFrame()),
        ]:
            sheet = writer.sheets[sheet_name]
            for i, col in enumerate(df.columns):
                width = max(12, len(str(col)) + 2)
                sheet.set_column(i, i, width)


# --------------------------------------------------
# Main
# --------------------------------------------------

def main():

    print("Reading reconciliation results...")
    results = read_reconciliation_results()

    print("Building summary...")
    summary = build_summary(results)

    print("Running quality checks for report...")
    bank, ledger = read_clean_data()
    issues = run_all_checks(bank, ledger)

    print(f"Writing report to {OUTPUT_PATH}...")
    write_report(summary, results, issues, OUTPUT_PATH)

    print()
    print("Report generated.")
    print(summary)

    # Небольшой JSON-совместимый словарь для Telegram-уведомления.
    # Не возвращаем DataFrame напрямую — Airflow не умеет сериализовать его в XCom.
    status_counts = results["status"].value_counts().to_dict()

    return {
        "total_records": int(len(results)),
        "status_counts": status_counts,
        "quality_issues_count": int(len(issues)),
        "total_discrepancy_amount": float(
            results["diff"].dropna().abs().sum()
        ),
    }


if __name__ == "__main__":
    main()
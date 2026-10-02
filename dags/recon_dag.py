import os
import sys
from datetime import datetime, timedelta

import requests
from airflow import DAG
from airflow.operators.python import PythonOperator

# Так DAG находит ваши скрипты в /opt/airflow/src
sys.path.append("/opt/airflow/src")

from load import main as run_load
from clean import main as run_clean
from reconcile import main as run_reconcile
from quality_checks import main as run_quality_checks
from report import main as run_report

from dotenv import load_dotenv
load_dotenv()


# --------------------------------------------------
# Telegram notification
# --------------------------------------------------

def notify_telegram(message: str) -> None:
    """
    Sends a plain text message to the configured Telegram chat.
    Wrapped in try/except so a Telegram outage never breaks the DAG itself —
    a failed notification shouldn't look like a failed pipeline.
    """

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print("Telegram credentials not set, skipping notification.")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"

    try:
        requests.post(url, data={"chat_id": chat_id, "text": message}, timeout=10)
    except Exception as e:
        print(f"Failed to send Telegram notification: {e}")


def notify_success(context) -> None:
    dag_id = context["dag"].dag_id
    dag_run = context["dag_run"]

    report_task_instance = dag_run.get_task_instance(task_id="generate_report")
    summary = report_task_instance.xcom_pull(task_ids="generate_report") if report_task_instance else None

    if not summary:
        notify_telegram(f"✅ {dag_id}: pipeline completed successfully (no summary available).")
        return

    status_lines = "\n".join(
        f"  • {status}: {count}"
        for status, count in summary.get("status_counts", {}).items()
    )

    message = (
        f"✅ {dag_id}: pipeline completed successfully.\n\n"
        f"Total records: {summary.get('total_records')}\n"
        f"{status_lines}\n\n"
        f"Data quality issues: {summary.get('quality_issues_count')}\n"
        f"Total discrepancy amount: {summary.get('total_discrepancy_amount'):.2f}"
    )

    notify_telegram(message)


def notify_failure(context) -> None:
    dag_id = context["dag"].dag_id
    task_id = context["task_instance"].task_id
    exception = context.get("exception")

    error_text = f"\nError: {exception}" if exception else ""

    message = (
        f"❌ {dag_id}: task '{task_id}' failed.{error_text}\n"
        f"Check Airflow logs for full traceback."
    )

    notify_telegram(message)


# --------------------------------------------------
# DAG definition
# --------------------------------------------------

default_args = {
    "owner": "mark",
    "retries": 1,
    "retry_delay": timedelta(minutes=2),
    "on_failure_callback": notify_failure,
}

with DAG(
    dag_id="recon_pipeline",
    default_args=default_args,
    description="Bank vs ledger reconciliation pipeline",
    schedule_interval=None,
    start_date=datetime(2026, 9, 1),
    catchup=False,
    on_success_callback=notify_success,
) as dag:

    load_task = PythonOperator(
        task_id="load_data",
        python_callable=run_load,
    )

    clean_task = PythonOperator(
        task_id="clean_data",
        python_callable=run_clean,
    )

    reconcile_task = PythonOperator(
        task_id="reconcile",
        python_callable=run_reconcile,
    )

    quality_task = PythonOperator(
        task_id="quality_checks",
        python_callable=run_quality_checks,
    )

    report_task = PythonOperator(
        task_id="generate_report",
        python_callable=run_report,
    )

    load_task >> clean_task >> reconcile_task >> quality_task >> report_task
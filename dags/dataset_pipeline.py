"""Manual-only orchestration until the source and update schedule are known."""

from datetime import datetime, timedelta, timezone

from airflow.decorators import dag, task


@dag(
    dag_id="dataset_pipeline",
    schedule=None,
    start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 1, "retry_delay": timedelta(minutes=1)},
    tags=["template", "manual"],
)
def dataset_pipeline():
    @task
    def ingest_validate_load_export():
        import logging

        from pipeline.core import connect, run

        engine = connect()
        try:
            result = run(engine)
            logging.info("Dataset pipeline: %s", result)
            return result
        finally:
            engine.dispose()

    ingest_validate_load_export()


dataset_pipeline()

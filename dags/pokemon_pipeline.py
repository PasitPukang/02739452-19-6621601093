"""Parallel TaskGroups, partial-source tolerance, quality branching and idempotent load."""

from datetime import datetime, timedelta, timezone

from airflow.decorators import dag, task
from airflow.models.param import Param
from airflow.operators.python import get_current_context
from airflow.utils.task_group import TaskGroup
from airflow.utils.trigger_rule import TriggerRule


@dag(
    dag_id="pokemon_pipeline", schedule=None,
    start_date=datetime(2026, 1, 1, tzinfo=timezone.utc), catchup=False, max_active_runs=1,
    default_args={"retries": 1, "retry_delay": timedelta(seconds=10)},
    params={
        "demo_fail_source": Param("none", enum=["none", "pokeapi", "pokemondb", "showdown"], description="Explicit simulated outage for assessment evidence"),
        "demo_bad_quality": Param(False, type="boolean", description="Explicitly inject an invalid merged total; originals and database stay intact"),
    },
    tags=["pokemon", "three-sources", "scraping", "quality"],
)
def pokemon_pipeline():
    @task
    def start():
        from pipeline.pokemon import begin_run, connect
        context = get_current_context()
        batch_id = context["run_id"]
        engine = connect()
        try:
            begin_run(engine, batch_id, dict(context["params"]))
        finally:
            engine.dispose()
        return batch_id

    @task
    def extract(source, batch_id):
        from pipeline.pokemon import connect, extract_source
        engine = connect()
        try:
            return extract_source(source, batch_id, engine, fail_source=get_current_context()["params"]["demo_fail_source"])
        finally:
            engine.dispose()

    @task(trigger_rule=TriggerRule.ALL_DONE)
    def transform(source, path, batch_id):
        from pipeline.pokemon import connect, transform_source
        engine = connect()
        try:
            return transform_source(source, path, batch_id, engine)
        finally:
            engine.dispose()

    @task(trigger_rule=TriggerRule.ALL_DONE)
    def merge_validate(paths, batch_id):
        from pipeline.pokemon import connect, merge_and_check
        engine = connect()
        try:
            return merge_and_check(paths, batch_id, engine, bad_quality=get_current_context()["params"]["demo_bad_quality"])
        finally:
            engine.dispose()

    @task.branch
    def quality_route(result):
        return "load_postgres" if result["passed"] else "quarantine"

    @task(task_id="load_postgres")
    def load(result, batch_id):
        from pipeline.pokemon import connect, load_merged
        engine = connect()
        try:
            return load_merged(result, batch_id, engine)
        finally:
            engine.dispose()

    @task(task_id="quarantine")
    def reject(result, batch_id):
        from pipeline.pokemon import connect, quarantine
        engine = connect()
        try:
            return quarantine(result, batch_id, engine)
        finally:
            engine.dispose()

    @task(trigger_rule=TriggerRule.ALL_DONE)
    def finish(batch_id):
        from pipeline.pokemon import connect, finish_run
        context = get_current_context()
        loading = context["ti"].xcom_pull(task_ids="load_postgres")
        engine = connect()
        try:
            result = finish_run(batch_id, engine, bool(loading))
        finally:
            engine.dispose()
        if result["status"] == "FAILED":
            raise RuntimeError("Pipeline failed; inspect upstream task logs and source audit")
        return result

    batch_id = start()
    cleaned = []
    for source in ("pokemondb", "pokeapi", "showdown"):
        with TaskGroup(group_id=f"source_{source}"):
            raw = extract(source, batch_id)
            cleaned.append(transform(source, raw, batch_id))
    result = merge_validate(cleaned, batch_id)
    route = quality_route(result)
    loaded = load(result, batch_id)
    rejected = reject(result, batch_id)
    route >> [loaded, rejected]
    [loaded, rejected] >> finish(batch_id)


pokemon_pipeline()

"""Explicit integration proof: run four real DAG scenarios on the project's PostgreSQL."""

import hashlib
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func, select

from pipeline.pokemon import connect, observations, pokemon, runs, source_runs


def snapshot(engine):
    with engine.connect() as conn:
        rows = [dict(r) for r in conn.execute(select(pokemon).order_by(pokemon.c.dex_id)).mappings()]
        count = conn.execute(select(func.count()).select_from(observations)).scalar_one()
    for row in rows:
        row.pop("updated_at")
    digest = hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()
    return {"canonical_rows": len(rows), "source_observations": count, "content_sha256": digest}


def main():
    from airflow.models.taskinstance import TaskInstance
    from airflow.settings import Session

    engine = connect()
    prefix = datetime.now(timezone.utc).strftime("%H%M%S")
    evidence = {"checked_at": datetime.now(timezone.utc).isoformat(), "initial": snapshot(engine), "cases": []}
    assert evidence["initial"]["canonical_rows"] == 151, "First run the normal DAG to populate actual public data"
    scenarios = [
        ("rerun", {}, "SUCCESS"),
        ("partial", {"demo_fail_source": "pokeapi"}, "PARTIAL"),
        ("quality", {"demo_bad_quality": True}, "REJECTED"),
        ("final", {}, "SUCCESS"),
    ]
    try:
        for name, conf, expected in scenarios:
            run_id = f"{name}_{prefix}"
            before = snapshot(engine)
            command = subprocess.run(["airflow", "dags", "trigger", "pokemon_pipeline", "--run-id", run_id,
                                      "--conf", json.dumps(conf)], capture_output=True, text=True)
            if command.returncode:
                raise RuntimeError(command.stderr[-1500:])
            print(f"Triggered {run_id}: {expected}", flush=True)
            deadline = time.monotonic() + 360
            while time.monotonic() < deadline:
                with engine.connect() as conn:
                    row = conn.execute(select(runs).where(runs.c.run_id == run_id)).mappings().first()
                if row and row["finished_at"]:
                    break
                time.sleep(2)
            else:
                raise TimeoutError(f"DAG {run_id} did not finish")
            assert row["status"] == expected, dict(row)
            after = snapshot(engine)
            assert after["canonical_rows"] == 151, after
            if name == "quality":
                assert before["content_sha256"] == after["content_sha256"], "Rejected run changed the canonical data"
            # Wait for Airflow to mark the final task before recording its task states.
            time.sleep(2)
            with Session() as session:
                task_rows = session.query(TaskInstance).filter(
                    TaskInstance.dag_id == "pokemon_pipeline", TaskInstance.run_id == run_id).all()
                states = {t.task_id: t.state for t in task_rows}
                timings = {t.task_id: {"start": str(t.start_date), "end": str(t.end_date)} for t in task_rows}
            assert states["quarantine" if name == "quality" else "load_postgres"] == "success", states
            assert states["load_postgres" if name == "quality" else "quarantine"] == "skipped", states
            if name == "partial":
                assert states["source_pokeapi.extract"] == "failed", states
                assert row["summary"]["input_rows"] == 302
            else:
                assert row["summary"]["input_rows"] == 453
            with engine.connect() as conn:
                sources = [dict(s) for s in conn.execute(select(source_runs).where(source_runs.c.run_id == run_id)).mappings()]
            evidence["cases"].append({"name": name, "run": dict(row), "before": before, "after": after,
                                      "task_states": states, "task_timings": timings, "sources": sources})
            print(f"Verified {run_id}: {expected}, 151 canonical rows", flush=True)
        target = Path("/opt/airflow/project/audit/pokemon_validation.json")
        target.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
        print("All live scenarios passed; evidence:", target, flush=True)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()

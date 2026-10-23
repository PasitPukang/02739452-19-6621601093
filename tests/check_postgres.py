"""Explicit integration check: TEST_POSTGRES_URL must point to an empty disposable DB."""

import json
import os
import tempfile
from pathlib import Path

from sqlalchemy import select

from pipeline.core import connect, records, run, status


def main():
    os.environ["DATABASE_URL"] = os.environ["TEST_POSTGRES_URL"]
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "config").mkdir()
        (root / "data/incoming").mkdir(parents=True)
        (root / "config/dataset.json").write_text(json.dumps(
            {"columns": ["id", "value"], "key_columns": ["id"]}), encoding="utf-8")
        source = root / "data/incoming/dataset.csv"
        engine = connect(root)
        try:
            assert engine.dialect.name == "postgresql"
            assert status(engine) == {"rows": 0, "latest_run": None}, "Use an empty disposable database"
            source.write_text("id,value\na,original\nb,ไทย\n", encoding="utf-8")
            run(engine, root)
            run(engine, root)
            assert status(engine)["rows"] == 2
            source.write_text("id,value\na,updated\n", encoding="utf-8")
            run(engine, root)
            assert status(engine)["rows"] == 2
            source.write_text("id,value\na,bad\na,duplicate\n", encoding="utf-8")
            try:
                run(engine, root)
            except ValueError:
                pass
            else:
                raise AssertionError("Duplicate input was accepted")
            with engine.connect() as conn:
                values = [json.loads(payload) for payload in conn.execute(select(records.c.payload)).scalars()]
            assert {row["id"]: row["value"] for row in values} == {"a": "updated", "b": "ไทย"}
            assert status(engine)["latest_run"]["status"] == "FAILED"
            assert (root / "powerbi/export/dataset.csv").exists()
            print("PostgreSQL integration passed: load, rerun, update, reject, audit, export")
        finally:
            engine.dispose()


if __name__ == "__main__":
    main()

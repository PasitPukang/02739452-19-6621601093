"""Validate before loading; retain raw input and an audit trail for every run."""

import csv
import hashlib
import io
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from sqlalchemy import Column, Integer, MetaData, String, Table, Text, create_engine, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

ROOT = Path(__file__).resolve().parents[1]
metadata = MetaData()
records = Table(
    "dataset_records", metadata,
    Column("record_key", String(64), primary_key=True),
    Column("payload", Text, nullable=False),
)
settings = Table(
    "dataset_settings", metadata,
    Column("name", String(30), primary_key=True),
    Column("value", Text, nullable=False),
)
audit = Table(
    "pipeline_run_audit", metadata,
    Column("run_id", String(32), primary_key=True),
    Column("started_at", String(40), nullable=False),
    Column("finished_at", String(40)),
    Column("status", String(20), nullable=False),
    Column("row_count", Integer, nullable=False),
    Column("stage", String(30), nullable=False),
    Column("message", Text, nullable=False),
)


def connect(root=ROOT):
    (root / "data").mkdir(parents=True, exist_ok=True)
    url = os.getenv("DATABASE_URL", f"sqlite:///{(root / 'data/project.sqlite').as_posix()}")
    engine = create_engine(url, future=True, pool_pre_ping=True)
    if engine.dialect.name not in {"sqlite", "postgresql"}:
        raise ValueError("Supported databases: SQLite and PostgreSQL")
    metadata.create_all(engine)
    return engine


def contract(root=ROOT):
    spec = json.loads((root / "config/dataset.json").read_text(encoding="utf-8"))
    columns, keys = spec.get("columns"), spec.get("key_columns")
    for name, values in (("columns", columns), ("key_columns", keys)):
        if not isinstance(values, list) or not values:
            raise ValueError(f"Configure non-empty {name} in config/dataset.json first")
        if any(not isinstance(v, str) or not v.strip() or v != v.strip() for v in values):
            raise ValueError(f"{name} must contain non-blank, trimmed column names")
        if len(values) != len(set(values)):
            raise ValueError(f"Duplicate names in {name}")
    if not set(keys) <= set(columns):
        raise ValueError("key_columns must be a subset of columns")
    return {"columns": columns, "key_columns": keys}


def validate(raw, spec):
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline=""), strict=True)
    if reader.fieldnames != spec["columns"]:
        raise ValueError("CSV header and order must exactly match configured columns")
    result, seen = [], set()
    # shortcut: a batch is held in memory, use streaming/staging for large datasets.
    for number, row in enumerate(reader, 2):
        if None in row or any(value is None for value in row.values()):
            raise ValueError(f"CSV row {number}: incorrect field count")
        row = {key: value.strip() for key, value in row.items()}
        if any(not row[key] for key in spec["key_columns"]):
            raise ValueError(f"CSV row {number}: empty key")
        key = hashlib.sha256(json.dumps(
            [row[k] for k in spec["key_columns"]], ensure_ascii=False,
        ).encode("utf-8")).hexdigest()
        if key in seen:
            raise ValueError(f"CSV row {number}: duplicate key in input")
        seen.add(key)
        result.append({"record_key": key, "payload": json.dumps(row, ensure_ascii=False)})
    if not result:
        raise ValueError("CSV contains no data rows")
    return result


def export_csv(engine, root=ROOT):
    with engine.connect() as conn:
        stored = conn.execute(select(settings.c.value).where(settings.c.name == "contract")).scalar()
        if stored is None:
            raise ValueError("No dataset has been loaded; export is unavailable")
        spec = json.loads(stored)
        target = root / "powerbi/export/dataset.csv"
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f".{uuid4().hex}.tmp")
        try:
            with temporary.open("w", encoding="utf-8-sig", newline="") as output:
                writer = csv.DictWriter(output, fieldnames=spec["columns"])
                writer.writeheader()
                for payload in conn.execute(select(records.c.payload).order_by(records.c.record_key)).scalars():
                    writer.writerow(json.loads(payload))
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
    return target


def run(engine, root=ROOT):
    run_id = uuid4().hex
    now = lambda: datetime.now(timezone.utc).isoformat()
    stage, count = "plan", 0
    with engine.begin() as conn:
        conn.execute(audit.insert().values(run_id=run_id, started_at=now(), status="RUNNING",
                                          row_count=0, stage=stage, message=""))
    try:
        spec = contract(root)
        stage = "extract_raw"
        raw = (root / "data/incoming/dataset.csv").read_bytes()
        raw_dir = root / "data/raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        (raw_dir / f"{run_id}.csv").write_bytes(raw)
        stage = "cleanse_validate"
        values = validate(raw, spec)
        count = len(values)
        cleaned_dir = root / "data/cleaned"
        cleaned_dir.mkdir(parents=True, exist_ok=True)
        (cleaned_dir / f"{run_id}.json").write_text(
            json.dumps(values, ensure_ascii=False), encoding="utf-8")
        stage = "load_validate"
        encoded = json.dumps(spec, sort_keys=True, ensure_ascii=False)
        with engine.begin() as conn:
            insert = pg_insert if conn.dialect.name == "postgresql" else sqlite_insert
            conn.execute(insert(settings).values(name="contract", value=encoded)
                         .on_conflict_do_nothing(index_elements=["name"]))
            stored = conn.execute(select(settings.c.value).where(settings.c.name == "contract")).scalar_one()
            if stored != encoded:
                raise ValueError("Contract changed: use a new database or plan a migration first")
            statement = insert(records)
            conn.execute(statement.on_conflict_do_update(
                index_elements=["record_key"], set_={"payload": statement.excluded.payload}), values)
            for value in values:
                saved = conn.execute(select(records.c.payload).where(
                    records.c.record_key == value["record_key"])).scalar_one()
                if saved != value["payload"]:
                    raise ValueError("Stored payload does not match validated input")
        stage = "export"
        export_csv(engine, root)
    except Exception as error:
        with engine.begin() as conn:
            conn.execute(audit.update().where(audit.c.run_id == run_id).values(
                finished_at=now(), status="FAILED", row_count=count, stage=stage,
                message=f"{type(error).__name__}: {error}"))
        raise
    with engine.begin() as conn:
        conn.execute(audit.update().where(audit.c.run_id == run_id).values(
            finished_at=now(), status="SUCCESS", row_count=count, stage="complete", message=""))
    return {"run_id": run_id, "status": "SUCCESS", "rows": count}


def status(engine):
    with engine.connect() as conn:
        count = conn.execute(select(func.count()).select_from(records)).scalar_one()
        latest = conn.execute(select(audit).order_by(audit.c.started_at.desc()).limit(1)).mappings().first()
    return {"rows": count, "latest_run": dict(latest) if latest else None}

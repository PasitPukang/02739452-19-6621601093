"""Three public sources, one canonical National Pokédex row per species."""

import csv
import hashlib
import json
import logging
import re
import threading
import time
import urllib.error
import urllib.request
import urllib.robotparser
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

from sqlalchemy import Column, Integer, JSON, String, Table, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from .core import ROOT, connect, metadata

SOURCES = {
    "pokemondb": "https://pokemondb.net/pokedex/all",
    "pokeapi": "https://pokeapi.co/api/v2/pokemon?limit=151&offset=0",
    "showdown": "https://play.pokemonshowdown.com/data/pokedex.json",
}
STATS = ("hp", "attack", "defense", "sp_attack", "sp_defense", "speed")
TYPES = set("normal fire water electric grass ice fighting poison ground flying psychic bug rock ghost dragon dark steel fairy".split())
pokemon = Table(
    "pokemon", metadata,
    Column("dex_id", Integer, primary_key=True),
    Column("name", String(80), nullable=False),
    Column("types", JSON, nullable=False),
    *[Column(stat, Integer, nullable=False) for stat in STATS],
    Column("total", Integer, nullable=False),
    Column("source_names", JSON, nullable=False),
    Column("source_urls", JSON, nullable=False),
    Column("conflicts", JSON, nullable=False),
    Column("updated_at", String(40), nullable=False),
)
observations = Table(
    "pokemon_observations", metadata,
    Column("source", String(20), primary_key=True),
    Column("dex_id", Integer, primary_key=True),
    Column("payload", JSON, nullable=False),
    Column("fetched_at", String(40), nullable=False),
)
runs = Table(
    "pokemon_runs", metadata,
    Column("run_id", String(250), primary_key=True),
    Column("started_at", String(40), nullable=False),
    Column("finished_at", String(40)),
    Column("status", String(20), nullable=False),
    Column("scenario", JSON, nullable=False),
    Column("summary", JSON, nullable=False),
)
source_runs = Table(
    "pokemon_source_runs", metadata,
    Column("run_id", String(250), primary_key=True),
    Column("source", String(20), primary_key=True),
    Column("status", String(20), nullable=False),
    Column("row_count", Integer, nullable=False),
    Column("message", String(1000), nullable=False),
    Column("started_at", String(40)),
    Column("finished_at", String(40)),
)


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def run_dir(run_id, root=ROOT):
    return root / "data/pokemon" / hashlib.sha256(run_id.encode()).hexdigest()[:24]


def upsert(conn, table, values, keys):
    if not values:
        return
    insert = pg_insert if conn.dialect.name == "postgresql" else sqlite_insert
    stmt = insert(table)
    conn.execute(stmt.on_conflict_do_update(
        index_elements=keys,
        set_={c.name: getattr(stmt.excluded, c.name) for c in table.c if c.name not in keys},
    ), values)


def begin_run(engine, run_id, scenario):
    with engine.begin() as conn:
        # Retrying start must not erase completed source evidence.
        insert = pg_insert if conn.dialect.name == "postgresql" else sqlite_insert
        conn.execute(insert(runs).values(run_id=run_id, started_at=utcnow(),
                     status="RUNNING", scenario=scenario, summary={})
                     .on_conflict_do_nothing(index_elements=["run_id"]))


def record_source(engine, run_id, source, status, count=0, message="", **times):
    with engine.begin() as conn:
        if "started_at" not in times:
            times["started_at"] = conn.execute(select(source_runs.c.started_at).where(
                source_runs.c.run_id == run_id, source_runs.c.source == source)).scalar()
        upsert(conn, source_runs, [dict(run_id=run_id, source=source, status=status,
               row_count=count, message=message[:1000], **times)], ["run_id", "source"])


class PublicFetcher:
    """Check each origin's robots rules, respect crawl-delay and cache API details."""

    agent = "BigDataPokemonProject"

    def __init__(self, directory, cache):
        self.directory, self.cache = directory, cache
        self.rules, self.locks, self.last = {}, {}, {}

    def request(self, url):
        request = urllib.request.Request(url, headers={
            "User-Agent": self.agent + "/1.0 (educational public game metadata)",
        })
        with urllib.request.urlopen(request, timeout=25) as response:
            if response.status != 200:
                raise ValueError(f"Unexpected HTTP {response.status}")
            return response.read().decode("utf-8")

    def get(self, url, cache=False):
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin not in self.rules:
            robots_url = origin + "/robots.txt"
            try:
                text = self.request(robots_url)
            except urllib.error.HTTPError as error:
                if error.code != 404:
                    raise
                text = ""  # HTTP 404: no robots resource, retained in the evidence.
            rule = urllib.robotparser.RobotFileParser(robots_url)
            rule.parse(text.splitlines())
            self.rules[origin] = rule
            self.locks[origin] = threading.Lock()
            self.last[origin] = time.monotonic()
            save_json(self.directory / (parts.netloc + ".robots.json"),
                      {"url": robots_url, "checked_at": utcnow(), "text": text})
        rule = self.rules[origin]
        if not rule.can_fetch(self.agent, url):
            raise ValueError(f"robots.txt disallows {url}")
        target = self.cache / (hashlib.sha256(url.encode()).hexdigest() + ".json")
        if cache and target.exists() and time.time() - target.stat().st_mtime < 86400:
            return target.read_text(encoding="utf-8")
        with self.locks[origin]:
            delay = rule.crawl_delay(self.agent) or 0
            time.sleep(max(0, delay - (time.monotonic() - self.last[origin])))
            text = self.request(url)
            self.last[origin] = time.monotonic()
        if cache:
            json.loads(text)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
        return text


def extract_source(source, run_id, engine, root=ROOT, fail_source="none"):
    if source not in SOURCES:
        raise ValueError("Unknown source")
    started = utcnow()
    record_source(engine, run_id, source, "EXTRACTING", started_at=started)
    directory = run_dir(run_id, root) / "raw"
    directory.mkdir(parents=True, exist_ok=True)
    try:
        if fail_source == source:
            raise ConnectionError(f"Demonstration: simulated {source} outage")
        fetcher = PublicFetcher(directory, root / "data/cache/pokeapi")
        text = fetcher.get(SOURCES[source])
        if source == "pokemondb":
            table = re.search(r'<table\b[^>]*id="pokedex".*?</table>', text, re.S)
            if not table:
                raise ValueError("Pokédex HTML table not found")
            # Retain only game metadata, not the surrounding page/scripts.
            payload = {"html": table.group(0)}
        elif source == "pokeapi":
            listing = json.loads(text)
            ids = [int(item["url"].rstrip("/").split("/")[-1]) for item in listing["results"]]
            if set(ids) != set(range(1, 152)) or len(ids) != 151:
                raise ValueError("PokeAPI list must contain IDs 1–151 exactly once")
            def detail(dex_id):
                return json.loads(fetcher.get(f"https://pokeapi.co/api/v2/pokemon/{dex_id}/", cache=True))
            with ThreadPoolExecutor(max_workers=4) as pool:
                payload = list(pool.map(detail, ids))
        else:
            payload = json.loads(text)
        path = save_json(directory / f"{source}.json",
                         {"source": source, "url": SOURCES[source], "fetched_at": utcnow(), "data": payload})
        return path
    except Exception as error:
        record_source(engine, run_id, source, "FAILED", message=f"{type(error).__name__}: {error}",
                      started_at=started, finished_at=utcnow())
        logging.exception("Source %s failed; other groups can continue", source)
        raise


class PokedexHTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows, self.cells, self.cell, self.form = [], None, None, False

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.cells, self.form = [], False
        elif tag == "td" and self.cells is not None:
            self.cell = []
        elif tag == "small" and self.cells is not None and len(self.cells) == 1:
            self.form = True

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag == "td" and self.cell is not None:
            self.cells.append(" ".join(" ".join(self.cell).split()))
            self.cell = None
        elif tag == "tr" and self.cells:
            self.rows.append((self.cells, self.form))
            self.cells = None


def normalize(source, payload):
    output = []
    if source == "pokemondb":
        parser = PokedexHTML()
        parser.feed(payload["html"])
        for cells, form in parser.rows:
            if form or not cells or not cells[0].isdigit() or not 1 <= int(cells[0]) <= 151:
                continue
            if len(cells) != 10:
                raise ValueError("Pokémon Database column layout changed")
            output.append(dict(dex_id=int(cells[0]), name=cells[1], types=[v.lower() for v in cells[2].split()],
                               total=int(cells[3]), **dict(zip(STATS, map(int, cells[4:10])))))
    elif source == "pokeapi":
        mapping = dict(zip(("hp", "attack", "defense", "special-attack", "special-defense", "speed"), STATS))
        for item in payload:
            stats = {mapping[s["stat"]["name"]]: int(s["base_stat"]) for s in item["stats"]}
            output.append(dict(dex_id=int(item["id"]), name=item["name"],
                               types=[t["type"]["name"] for t in sorted(item["types"], key=lambda t: t["slot"])],
                               total=sum(stats.values()), **stats))
    elif source == "showdown":
        mapping = dict(zip(("hp", "atk", "def", "spa", "spd", "spe"), STATS))
        for item in payload.values():
            if not 1 <= item.get("num", 0) <= 151 or item.get("forme"):
                continue
            stats = {mapping[k]: int(v) for k, v in item["baseStats"].items()}
            output.append(dict(dex_id=int(item["num"]), name=item["name"],
                               types=[t.lower() for t in item["types"]], total=sum(stats.values()), **stats))
    else:
        raise ValueError("Unknown source")
    return output


def transform_source(source, raw_path, run_id, engine, root=ROOT):
    if not raw_path:
        return None
    try:
        raw = json.loads(Path(raw_path).read_text(encoding="utf-8"))
        rows = normalize(source, raw["data"])
        if not rows:
            raise ValueError("Source yielded no base species")
        for row in rows:
            row.update(source=source, source_url=(f"https://pokeapi.co/api/v2/pokemon/{row['dex_id']}/"
                       if source == "pokeapi" else SOURCES[source]), fetched_at=raw["fetched_at"])
        path = save_json(run_dir(run_id, root) / f"{source}.cleaned.json", rows)
        record_source(engine, run_id, source, "SUCCESS", len(rows), finished_at=utcnow())
        return path
    except Exception as error:
        record_source(engine, run_id, source, "FAILED", message=f"Transform: {error}", finished_at=utcnow())
        raise


def row_errors(row):
    errors = []
    if type(row.get("dex_id")) is not int or not 1 <= row["dex_id"] <= 151:
        errors.append("dex_id must be 1–151")
    if not isinstance(row.get("name"), str) or not row["name"].strip():
        errors.append("name is empty")
    types = row.get("types")
    if not isinstance(types, list) or not 1 <= len(types) <= 2 or len(set(types)) != len(types) or not set(types) <= TYPES:
        errors.append("invalid Pokémon types")
    if any(type(row.get(s)) is not int or not 1 <= row[s] <= 255 for s in STATS):
        errors.append("base stats must be integers 1–255")
    elif type(row.get("total")) is not int or row["total"] != sum(row[s] for s in STATS):
        errors.append("total differs from sum of six stats")
    return errors


def merge_and_check(paths, run_id, engine, root=ROOT, bad_quality=False):
    values = [row for path in paths if path for row in json.loads(Path(path).read_text(encoding="utf-8"))]
    errors, groups, seen = [], {}, set()
    for row in values:
        errors.extend(f"{row.get('source')} #{row.get('dex_id')}: {e}" for e in row_errors(row))
        key = (row["source"], row["dex_id"])
        if key in seen:
            errors.append(f"Duplicate within source: {key}")
        seen.add(key)
        groups.setdefault(row["dex_id"], []).append(row)
    merged = []
    priority = {"pokeapi": 0, "pokemondb": 1, "showdown": 2}
    for dex_id, items in sorted(groups.items()):
        items.sort(key=lambda row: priority[row["source"]])
        best = items[0]
        row = {key: best[key] for key in ("dex_id", "name", "types", "total", *STATS)}
        # A display name is metadata; never use name spelling as the dedup key.
        row["name"] = next((v["name"] for v in items if v["source"] == "pokemondb"), best["name"])
        row["source_names"] = sorted({v["source"] for v in items})
        row["source_urls"] = {v["source"]: v["source_url"] for v in items}
        row["conflicts"] = {key: {v["source"]: v[key] for v in items} for key in (*STATS, "types")
                            if len({json.dumps(v[key]) for v in items}) > 1}
        row["updated_at"] = utcnow()
        merged.append(row)
    if bad_quality and merged:
        merged[0]["total"] = -1  # Explicit demo parameter; originals remain in raw/cleaned files.
    if len(merged) < 100:
        errors.append(f"Only {len(merged)} unique species; minimum is 100")
    for row in merged:
        errors.extend(f"Merged #{row['dex_id']}: {e}" for e in row_errors(row))
    summary = {"input_rows": len(values), "unique_rows": len(merged),
               "duplicates_removed": len(values) - len(merged),
               "conflict_rows": sum(bool(row["conflicts"]) for row in merged),
               "successful_sources": sorted({v["source"] for v in values}),
               "missing_ids": sorted(set(range(1, 152)) - set(groups)), "errors": errors,
               "passed": not errors}
    path = save_json(run_dir(run_id, root) / "merged.json", {"rows": merged, "observations": values, "quality": summary})
    with engine.begin() as conn:
        conn.execute(runs.update().where(runs.c.run_id == run_id).values(summary=summary))
    return {"path": path, "passed": summary["passed"], "unique_rows": len(merged), "errors": errors}


def load_merged(result, run_id, engine, root=ROOT):
    data = json.loads(Path(result["path"]).read_text(encoding="utf-8"))
    if not data["quality"]["passed"] or any(row_errors(row) for row in data["rows"]):
        raise ValueError("Refusing unvalidated data")
    with engine.begin() as conn:
        upsert(conn, pokemon, data["rows"], ["dex_id"])
        upsert(conn, observations, [dict(source=v["source"], dex_id=v["dex_id"], payload=v,
                                       fetched_at=v["fetched_at"]) for v in data["observations"]], ["source", "dex_id"])
        for row in data["rows"]:
            saved = conn.execute(select(pokemon).where(pokemon.c.dex_id == row["dex_id"])).mappings().one()
            if any(saved[s] != row[s] for s in STATS):
                raise ValueError("Post-load verification failed")
    target = root / "powerbi/export/pokemon.csv"
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix(".csv.tmp")
    try:
        with temp.open("w", encoding="utf-8-sig", newline="") as file:
            fields = ["dex_id", "name", "types", *STATS, "total", "source_names", "updated_at"]
            writer = csv.DictWriter(file, fields, extrasaction="ignore")
            writer.writeheader()
            for row in data["rows"]:
                writer.writerow({**row, "types": "/".join(row["types"]), "source_names": "/".join(row["source_names"])})
        temp.replace(target)
    finally:
        temp.unlink(missing_ok=True)
    return {"loaded": len(data["rows"])}


def quarantine(result, run_id, engine, root=ROOT):
    data = json.loads(Path(result["path"]).read_text(encoding="utf-8"))
    save_json(run_dir(run_id, root) / "quarantine.json", data)
    with engine.begin() as conn:
        conn.execute(runs.update().where(runs.c.run_id == run_id).values(status="REJECTED"))
    return {"rejected": True, "errors": result["errors"]}


def finish_run(run_id, engine, loaded):
    with engine.begin() as conn:
        run = conn.execute(select(runs).where(runs.c.run_id == run_id)).mappings().one()
        sources = conn.execute(select(source_runs).where(source_runs.c.run_id == run_id)).mappings().all()
        state = run["status"]
        if state != "REJECTED":
            state = ("PARTIAL" if len(sources) < 3 or any(s["status"] != "SUCCESS" for s in sources) else "SUCCESS") if loaded else "FAILED"
        conn.execute(runs.update().where(runs.c.run_id == run_id).values(status=state, finished_at=utcnow()))
    return {"status": state, "loaded": loaded}


def dashboard(engine, filters=None):
    filters = filters or {}
    with engine.connect() as conn:
        all_rows = [dict(row) for row in conn.execute(select(pokemon).order_by(pokemon.c.dex_id)).mappings()]
    rows = all_rows
    if filters.get("q"):
        query = filters["q"].lower()[:100]
        rows = [r for r in rows if query in r["name"].lower() or query == str(r["dex_id"])]
    if filters.get("type"):
        if filters["type"] not in TYPES:
            raise ValueError("Unknown type")
        rows = [r for r in rows if filters["type"] in r["types"]]
    if filters.get("source"):
        if filters["source"] not in SOURCES:
            raise ValueError("Unknown source")
        rows = [r for r in rows if filters["source"] in r["source_names"]]
    if filters.get("min_total"):
        minimum = int(filters["min_total"])
        if not 0 <= minimum <= 1530:
            raise ValueError("min_total must be 0–1530")
        rows = [r for r in rows if r["total"] >= minimum]
    sort = filters.get("sort", "dex_id")
    if sort not in {"dex_id", "total", "attack", "defense", "speed"}:
        raise ValueError("Unknown sort field")
    rows.sort(key=lambda r: (r[sort], -r["dex_id"]) if sort != "dex_id" else r[sort], reverse=sort != "dex_id")
    return {"rows": rows, "kpi": {"total_species": len(all_rows), "filtered_species": len(rows),
             "average_total": round(sum(r["total"] for r in rows) / len(rows), 1) if rows else None,
             "conflict_rows": sum(bool(r["conflicts"]) for r in rows)},
            "types": sorted({t for r in all_rows for t in r["types"]}),
            "type_counts": dict(Counter(t for r in rows for t in r["types"])),
            "top_stats": sorted(rows, key=lambda r: (-r["total"], r["dex_id"]))[:10]}


def pipeline_status(engine):
    with engine.connect() as conn:
        history = [dict(r) for r in conn.execute(select(runs).order_by(runs.c.started_at.desc()).limit(10)).mappings()]
        sources = [dict(r) for r in conn.execute(select(source_runs).where(
            source_runs.c.run_id == history[0]["run_id"])).mappings()] if history else []
    return {"runs": history, "sources": sources}

import json
import ast
import os
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import func, select

from pipeline.pokemon import (
    STATS, PublicFetcher, begin_run, connect, dashboard, finish_run, load_merged,
    merge_and_check, normalize, observations, pokemon, quarantine, record_source,
    row_errors, save_json, pipeline_status, transform_source,
)


def example(dex_id=1, source="pokeapi"):
    return dict(dex_id=dex_id, name=f"species-{dex_id}", types=["grass"], total=300,
                **dict.fromkeys(STATS, 50), source=source,
                source_url="https://pokeapi.co/", fetched_at="2026-10-23T00:00:00+00:00")


class PokemonTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.env = patch.dict(os.environ)
        self.env.start()
        os.environ.pop("DATABASE_URL", None)
        self.engine = connect(self.root)
        begin_run(self.engine, "test", {})

    def tearDown(self):
        self.engine.dispose()
        self.env.stop()
        self.directory.cleanup()

    def batch(self, source, size=151):
        return save_json(self.root / f"{source}.json", [example(i, source) for i in range(1, size + 1)])

    def test_merge_deduplicate_and_upsert(self):
        paths = [self.batch(s) for s in ("pokeapi", "pokemondb", "showdown")]
        result = merge_and_check(paths, "test", self.engine, self.root)
        self.assertTrue(result["passed"])
        quality = json.loads(Path(result["path"]).read_text())["quality"]
        self.assertEqual((quality["input_rows"], quality["unique_rows"], quality["duplicates_removed"]), (453, 151, 302))
        load_merged(result, "test", self.engine, self.root)
        load_merged(result, "test", self.engine, self.root)
        with self.engine.connect() as conn:
            self.assertEqual(conn.execute(select(func.count()).select_from(pokemon)).scalar(), 151)
            self.assertEqual(conn.execute(select(func.count()).select_from(observations)).scalar(), 453)
        self.assertEqual(dashboard(self.engine)["kpi"]["total_species"], 151)

    def test_partial_source_and_finish(self):
        record_source(self.engine, "test", "pokeapi", "FAILED", message="simulated outage")
        for source in ("pokemondb", "showdown"):
            record_source(self.engine, "test", source, "SUCCESS", 151)
        result = merge_and_check([None, self.batch("pokemondb"), self.batch("showdown")], "test", self.engine, self.root)
        self.assertTrue(result["passed"])
        load_merged(result, "test", self.engine, self.root)
        self.assertEqual(finish_run("test", self.engine, True)["status"], "PARTIAL")
        self.assertEqual(dashboard(self.engine)["rows"][0]["source_names"], ["pokemondb", "showdown"])

    def test_quality_rejection_preserves_database(self):
        path = self.batch("pokeapi")
        valid = merge_and_check([path], "test", self.engine, self.root)
        load_merged(valid, "test", self.engine, self.root)
        invalid = merge_and_check([path], "test", self.engine, self.root, bad_quality=True)
        self.assertFalse(invalid["passed"])
        with self.assertRaises(ValueError):
            load_merged(invalid, "test", self.engine, self.root)
        quarantine(invalid, "test", self.engine, self.root)
        self.assertEqual(finish_run("test", self.engine, False)["status"], "REJECTED")
        self.assertEqual(dashboard(self.engine)["rows"][0]["total"], 300)

    def test_all_sources_down_or_below_minimum_reject(self):
        for paths in ([None, None, None], [self.batch("pokeapi", 99)]):
            result = merge_and_check(paths, "test", self.engine, self.root)
            self.assertFalse(result["passed"])
            self.assertTrue(any("minimum" in error for error in result["errors"]))

    def test_duplicate_within_source_is_not_silently_removed(self):
        path = save_json(self.root / "duplicate.json", [example(), example()])
        result = merge_and_check([path], "test", self.engine, self.root)
        self.assertTrue(any("Duplicate within source" in e for e in result["errors"]))

    def test_conflicting_stats_have_visible_provenance(self):
        paths = [self.batch("pokeapi"), self.batch("showdown")]
        rows = json.loads(Path(paths[1]).read_text())
        rows[0].update(hp=51, total=301)
        save_json(Path(paths[1]), rows)
        result = merge_and_check(paths, "test", self.engine, self.root)
        data = json.loads(Path(result["path"]).read_text())
        self.assertTrue(result["passed"])
        self.assertEqual(data["rows"][0]["hp"], 50)
        self.assertEqual(data["rows"][0]["conflicts"]["hp"], {"pokeapi": 50, "showdown": 51})

    def test_html_parser_excludes_forms_and_checks_layout(self):
        cells = '<td>0001</td><td>Bulbasaur{}</td><td>Grass<br>Poison</td><td>318</td><td>45</td><td>49</td><td>49</td><td>65</td><td>65</td><td>45</td>'
        html = '<table><tr>' + cells.format('') + '</tr><tr>' + cells.format('<small>Mega form</small>') + '</tr></table>'
        rows = normalize("pokemondb", {"html": html})
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["types"], ["grass", "poison"])
        self.assertEqual(row_errors(rows[0]), [])
        with self.assertRaises(ValueError):
            normalize("pokemondb", {"html": '<tr><td>0001</td><td>Changed layout</td></tr>'})

    def test_source_normalizers_same_stats(self):
        api = {"id": 1, "name": "bulbasaur", "types": [{"slot": 1, "type": {"name": "grass"}}],
               "stats": [{"stat": {"name": s}, "base_stat": 50} for s in ("hp", "attack", "defense", "special-attack", "special-defense", "speed")]}
        showdown = {"bulbasaur": {"num": 1, "name": "Bulbasaur", "types": ["Grass"],
                                  "baseStats": dict.fromkeys(("hp", "atk", "def", "spa", "spd", "spe"), 50)}}
        a, b = normalize("pokeapi", [api])[0], normalize("showdown", showdown)[0]
        self.assertEqual({s: a[s] for s in STATS}, {s: b[s] for s in STATS})
        self.assertEqual(row_errors(a), [])

    def test_robots_denial_and_api_cache(self):
        fetcher = PublicFetcher(self.root / "raw", self.root / "cache")
        with patch.object(fetcher, "request", return_value="User-agent: *\nDisallow: /blocked\n") as request:
            with self.assertRaisesRegex(ValueError, "robots"):
                fetcher.get("https://example.org/blocked")
            self.assertEqual(request.call_count, 1)
        fetcher = PublicFetcher(self.root / "raw", self.root / "cache")
        with patch.object(fetcher, "request", side_effect=["User-agent: *\nAllow: /", '{"id":1}']) as request:
            self.assertEqual(fetcher.get("https://example.org/data", cache=True), '{"id":1}')
            self.assertEqual(fetcher.get("https://example.org/data", cache=True), '{"id":1}')
            self.assertEqual(request.call_count, 2)

    def test_invalid_stat_types_and_filters(self):
        for changes in ({"hp": -1}, {"total": 301}, {"types": ["not-a-type"]}, {"dex_id": 152}, {"hp": True}):
            row = example()
            row.update(changes)
            self.assertTrue(row_errors(row))
        valid = merge_and_check([self.batch("pokeapi")], "test", self.engine, self.root)
        load_merged(valid, "test", self.engine, self.root)
        self.assertEqual(len(dashboard(self.engine, {"q": "species-25", "type": "grass"})["rows"]), 1)
        for filters in ({"sort": "DROP TABLE"}, {"source": "unknown"}, {"type": "unknown"}, {"min_total": "-1"}):
            with self.assertRaises(ValueError):
                dashboard(self.engine, filters)

    def test_missing_source_result_does_not_fail_transform(self):
        self.assertIsNone(transform_source("pokeapi", None, "test", self.engine, self.root))

    def test_audit_retains_extraction_start(self):
        record_source(self.engine, "test", "pokeapi", "EXTRACTING", started_at="2026-10-23T00:00:00+00:00")
        record_source(self.engine, "test", "pokeapi", "SUCCESS", 151, finished_at="2026-10-23T00:01:00+00:00")
        self.assertEqual(pipeline_status(self.engine)["sources"][0]["started_at"], "2026-10-23T00:00:00+00:00")

    def test_taskflow_arguments_do_not_shadow_airflow_context(self):
        tree = ast.parse((Path(__file__).parents[1] / "dags/pokemon_pipeline.py").read_text(encoding="utf-8"))
        reserved = {"run_id", "dag_run", "ti", "params", "execution_date"}
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                self.assertFalse({arg.arg for arg in node.args.args} & reserved, node.name)


if __name__ == "__main__":
    unittest.main()

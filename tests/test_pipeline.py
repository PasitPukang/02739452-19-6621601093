import csv
import json
import os
import tempfile
import threading
import unittest
from http.server import HTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import urlopen

from sqlalchemy import select

from pipeline.core import connect, contract, export_csv, records, run, status, validate
from web.app import Handler


class PipelineTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.env = patch.dict(os.environ)
        self.env.start()
        os.environ.pop("DATABASE_URL", None)
        (self.root / "config").mkdir()
        (self.root / "data/incoming").mkdir(parents=True)
        self.spec = {"columns": ["id", "value"], "key_columns": ["id"]}
        self.write_spec(self.spec)
        self.engine = connect(self.root)

    def tearDown(self):
        self.engine.dispose()
        self.env.stop()
        self.temp.cleanup()

    def write_spec(self, spec):
        (self.root / "config/dataset.json").write_text(json.dumps(spec), encoding="utf-8")

    def write_csv(self, text):
        (self.root / "data/incoming/dataset.csv").write_text(text, encoding="utf-8-sig")

    def test_empty_state_does_not_invent_data(self):
        self.assertEqual(status(self.engine), {"rows": 0, "latest_run": None})
        self.write_spec({"columns": [], "key_columns": []})
        with self.assertRaisesRegex(ValueError, "Configure"):
            run(self.engine, self.root)
        latest = status(self.engine)["latest_run"]
        self.assertEqual((latest["status"], latest["stage"]), ("FAILED", "plan"))
        with self.assertRaisesRegex(ValueError, "No dataset"):
            export_csv(self.engine, self.root)

    def test_rerun_upsert_and_export(self):
        self.write_csv('id,value\na, สวัสดี \nb,"with,comma"\n')
        run(self.engine, self.root)
        run(self.engine, self.root)
        self.assertEqual(status(self.engine)["rows"], 2)
        self.write_csv("id,value\na,updated\n")
        run(self.engine, self.root)
        self.assertEqual(status(self.engine)["rows"], 2)
        target = self.root / "powerbi/export/dataset.csv"
        with target.open(encoding="utf-8-sig", newline="") as source:
            rows = {row["id"]: row["value"] for row in csv.DictReader(source)}
        self.assertEqual(rows, {"a": "updated", "b": "with,comma"})
        self.assertEqual(len(list((self.root / "data/raw").glob("*.csv"))), 3)
        self.assertEqual(status(self.engine)["latest_run"]["status"], "SUCCESS")

    def test_bad_input_does_not_modify_existing_data(self):
        self.write_csv("id,value\na,original\n")
        run(self.engine, self.root)
        target = self.root / "powerbi/export/dataset.csv"
        original = target.read_bytes()
        for text in ["id,value\na,new\na,duplicate\n", "id,value\n,empty\n",
                     "value,id\nwrong,a\n", "id,value\na,too,many\n",
                     "id,value\na\n", "id,value\n", 'id,value\na,"unfinished\n']:
            with self.subTest(text=text):
                self.write_csv(text)
                with self.assertRaises((ValueError, csv.Error)):
                    run(self.engine, self.root)
                self.assertEqual(status(self.engine)["rows"], 1)
                self.assertEqual(target.read_bytes(), original)
                self.assertEqual(status(self.engine)["latest_run"]["status"], "FAILED")
        with self.engine.connect() as conn:
            self.assertEqual(json.loads(conn.execute(select(records.c.payload)).scalar_one())["value"], "original")

    def test_changed_contract_is_rejected(self):
        self.write_csv("id,value\na,original\n")
        run(self.engine, self.root)
        self.write_spec({"columns": ["id", "value"], "key_columns": ["value"]})
        with self.assertRaisesRegex(ValueError, "Contract changed"):
            run(self.engine, self.root)
        self.assertEqual(status(self.engine)["rows"], 1)

    def test_contract_boundary_and_bom(self):
        for spec in [{"columns": ["id", "id"], "key_columns": ["id"]},
                     {"columns": ["id"], "key_columns": ["missing"]},
                     {"columns": [None], "key_columns": ["id"]},
                     {"columns": [" id"], "key_columns": [" id"]}]:
            self.write_spec(spec)
            with self.assertRaises(ValueError):
                contract(self.root)
        values = validate("\ufeffid,value\na, ไทย\n".encode("utf-8"), self.spec)
        self.assertEqual(json.loads(values[0]["payload"])["value"], "ไทย")

    def test_export_failure_is_audited_and_can_be_retried(self):
        self.write_csv("id,value\na,original\n")
        with patch("pipeline.core.export_csv", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                run(self.engine, self.root)
        state = status(self.engine)
        self.assertEqual(state["rows"], 1)
        self.assertEqual((state["latest_run"]["status"], state["latest_run"]["stage"]), ("FAILED", "export"))
        run(self.engine, self.root)
        self.assertEqual(status(self.engine)["rows"], 1)
        self.assertEqual(status(self.engine)["latest_run"]["status"], "SUCCESS")

    def test_missing_input_is_audited(self):
        with self.assertRaises(FileNotFoundError):
            run(self.engine, self.root)
        self.assertEqual(status(self.engine)["latest_run"]["stage"], "extract_raw")

    def test_dashboard_http_empty_and_not_found(self):
        server = HTTPServer(("127.0.0.1", 0), Handler)
        server.engine = self.engine
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            with urlopen(base + "/api/status") as response:
                self.assertEqual(json.load(response), {"rows": 0, "latest_run": None})
            with urlopen(base + "/") as response:
                self.assertIn("รอชุดข้อมูลของคุณ", response.read().decode("utf-8"))
            with urlopen(base + "/assets/25.png") as response:
                self.assertEqual(response.headers['Content-Type'], 'image/png')
                self.assertTrue(response.read().startswith(b'\x89PNG\r\n\x1a\n'))
            for blocked in ["/assets/../.env", "/assets/unknown.png"]:
                with self.assertRaises(HTTPError) as error:
                    urlopen(base + blocked)
                self.assertEqual(error.exception.code, 404)
                error.exception.close()
            with self.assertRaises(HTTPError) as error:
                urlopen(base + "/unknown")
            self.assertEqual(error.exception.code, 404)
            error.exception.close()
        finally:
            server.shutdown()
            thread.join()
            server.server_close()


if __name__ == "__main__":
    unittest.main()

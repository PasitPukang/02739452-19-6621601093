"""Local dashboard reading Pokémon and pipeline status from the database."""

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from pipeline.core import connect, status
from pipeline.pokemon import dashboard, pipeline_status


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlsplit(self.path)
        if path.path == "/":
            content = Path(__file__).with_name("index.html").read_bytes()
            content_type = "text/html; charset=utf-8"
        elif path.path in {"/assets/1.png", "/assets/4.png", "/assets/7.png", "/assets/25.png"}:
            content = (Path(__file__).parent / path.path.lstrip("/")).read_bytes()
            content_type = "image/png"
        elif path.path in {"/api/status", "/api/pokemon", "/api/pipeline"}:
            try:
                if path.path == "/api/pokemon":
                    filters = {k: v[0] for k, v in parse_qs(path.query).items()}
                    result = dashboard(self.server.engine, filters)
                elif path.path == "/api/pipeline":
                    result = pipeline_status(self.server.engine)
                else:
                    result = status(self.server.engine)
                # Error details remain in the database/CLI rather than the public status page.
                if result.get("latest_run"):
                    result["latest_run"].pop("message", None)
                content = json.dumps(result).encode("utf-8")
            except ValueError:
                self.send_error(400, "Invalid filter")
                return
            except Exception:
                self.send_error(503, "Database unavailable")
                return
            content_type = "application/json"
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)


if __name__ == "__main__":
    import os

    server = HTTPServer((os.getenv("WEB_HOST", "127.0.0.1"), 8091), Handler)
    server.engine = connect()
    print("Project status: http://localhost:8091", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        server.engine.dispose()

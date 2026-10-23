"""Run from the project root: python -m pipeline.cli init|run|status|export."""

import argparse
import csv
import json
import sys

from .core import connect, export_csv, run, status


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["init", "run", "status", "export"])
    command = parser.parse_args().command
    engine = connect()
    try:
        if command == "run":
            result = run(engine)
        elif command == "export":
            result = {"export": str(export_csv(engine))}
        else:
            result = status(engine)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, OSError, csv.Error) as error:
        print(str(error), file=sys.stderr)
        return 1
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

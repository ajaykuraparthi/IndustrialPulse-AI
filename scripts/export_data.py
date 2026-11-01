"""Export generated seed SQL and persisted simulation results."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from app.exports import export_seed_json, export_seed_sql, export_simulation_results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default=str(ROOT_DIR / "data" / "generated"))
    parser.add_argument("--database", default=str(ROOT_DIR / "industrialpulse.db"))
    parser.add_argument("--seed-json", help="Output path for generated seed data as JSON")
    parser.add_argument("--seed-sql", help="Output path for importable SQLite seed SQL")
    parser.add_argument(
        "--simulation-exports",
        help="Directory for simulation_runs and alarms CSV/JSON exports",
    )
    args = parser.parse_args()
    if not args.seed_json and not args.seed_sql and not args.simulation_exports:
        parser.error("select --seed-json, --seed-sql, and/or --simulation-exports")

    if args.seed_json:
        path = export_seed_json(args.data_dir, args.seed_json)
        print(f"Seed JSON: {path}")
    if args.seed_sql:
        path = export_seed_sql(args.data_dir, args.seed_sql)
        print(f"SQLite seed SQL: {path}")
    if args.simulation_exports:
        paths = export_simulation_results(args.database, args.simulation_exports)
        for name, path in paths.items():
            print(f"{name}: {path}")


if __name__ == "__main__":
    main()

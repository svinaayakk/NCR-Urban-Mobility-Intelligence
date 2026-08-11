"""Run named SQL business queries and export their results as CSV files."""

from __future__ import annotations

from pathlib import Path
import re
import sqlite3

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATABASE = PROJECT_ROOT / "outputs" / "database" / "ncrmove.sqlite"
QUERY_FILE = PROJECT_ROOT / "sql" / "business_metrics.sql"
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "sql"


def parse_named_queries(sql: str) -> dict[str, str]:
    parts = re.split(r"-- name: ([a-z_]+)\n", sql)
    return {parts[index]: parts[index + 1].strip() for index in range(1, len(parts), 2)}


def main() -> None:
    if not DATABASE.exists():
        raise FileNotFoundError("Database is missing. Run python3 python/database/load_sqlite.py first.")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    queries = parse_named_queries(QUERY_FILE.read_text(encoding="utf-8"))
    with sqlite3.connect(DATABASE) as connection:
        for name, query in queries.items():
            result = pd.read_sql_query(query, connection)
            result.to_csv(OUTPUT_DIR / f"{name}.csv", index=False)
            print(f"{name}: {len(result):,} rows")


if __name__ == "__main__":
    main()

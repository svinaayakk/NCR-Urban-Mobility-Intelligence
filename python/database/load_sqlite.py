"""Build a local SQLite analytics database from the NCRMove raw and cleaned files."""

from __future__ import annotations

from pathlib import Path
import sqlite3

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DATA = PROJECT_ROOT / "data" / "raw"
CLEANED_TRIPS = PROJECT_ROOT / "outputs" / "cleaning" / "trips_cleaned.csv"
DATABASE = PROJECT_ROOT / "outputs" / "database" / "ncrmove.sqlite"
SCHEMA = PROJECT_ROOT / "sql" / "schema.sql"

TABLE_FILES = {
    "zones": RAW_DATA / "zones.csv",
    "vehicles": RAW_DATA / "vehicles.csv",
    "drivers": RAW_DATA / "drivers.csv",
    "weather": RAW_DATA / "weather.csv",
    "events": RAW_DATA / "events.csv",
    "traffic": RAW_DATA / "traffic.csv",
    "demand_supply": RAW_DATA / "demand_supply.csv",
}


def load_table(connection: sqlite3.Connection, table: str, path: Path, chunksize: int | None = None) -> None:
    reader = pd.read_csv(path, chunksize=chunksize) if chunksize else [pd.read_csv(path)]
    for frame in reader:
        frame.to_sql(table, connection, if_exists="append", index=False, method="multi", chunksize=5_000)


def main() -> None:
    if not CLEANED_TRIPS.exists():
        raise FileNotFoundError("Run python3 python/data_cleaning/clean_trips.py before loading the database.")
    DATABASE.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DATABASE) as connection:
        connection.executescript(SCHEMA.read_text(encoding="utf-8"))
        for table, path in TABLE_FILES.items():
            load_table(connection, table, path, chunksize=100_000 if table in {"traffic", "demand_supply"} else None)
        load_table(connection, "trips", CLEANED_TRIPS, chunksize=100_000)
        table_counts = pd.read_sql_query(
            "SELECT 'trips' AS table_name, COUNT(*) AS rows FROM trips "
            "UNION ALL SELECT 'demand_supply', COUNT(*) FROM demand_supply "
            "UNION ALL SELECT 'traffic', COUNT(*) FROM traffic",
            connection,
        )
    print(f"SQLite database created: {DATABASE}")
    print(table_counts.to_string(index=False))


if __name__ == "__main__":
    main()

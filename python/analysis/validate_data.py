"""Validate the NCRMove synthetic raw datasets and generate a QA report.

Raw files are read only. Outputs are written to outputs/validation/.
"""

from __future__ import annotations

from pathlib import Path
import json

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DATA = PROJECT_ROOT / "data" / "raw"
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "validation"

FILES = [
    "zones",
    "vehicles",
    "drivers",
    "weather",
    "events",
    "traffic",
    "demand_supply",
    "trips",
    "trips_messy",
]

DATETIME_COLUMNS = {
    "vehicles": ["join_date"],
    "drivers": ["join_date"],
    "weather": ["timestamp"],
    "events": ["event_date"],
    "traffic": ["timestamp"],
    "demand_supply": ["timestamp"],
    "trips": ["request_timestamp", "pickup_timestamp", "dropoff_timestamp"],
    "trips_messy": ["request_timestamp", "pickup_timestamp", "dropoff_timestamp"],
}


def load_data() -> dict[str, pd.DataFrame]:
    """Load each CSV and parse fields that represent dates or timestamps."""
    tables: dict[str, pd.DataFrame] = {}
    for name in FILES:
        path = RAW_DATA / f"{name}.csv"
        if not path.exists():
            raise FileNotFoundError(f"Expected source file is missing: {path}")
        tables[name] = pd.read_csv(path, parse_dates=DATETIME_COLUMNS.get(name, []))
    return tables


def pct(value: float) -> str:
    return f"{value:.2%}"


def write_data_profile(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for name, frame in tables.items():
        rows.append(
            {
                "dataset": name,
                "rows": len(frame),
                "columns": len(frame.columns),
                "duplicate_rows": int(frame.duplicated().sum()),
                "missing_cells": int(frame.isna().sum().sum()),
            }
        )
    profile = pd.DataFrame(rows)
    profile.to_csv(OUTPUT_DIR / "dataset_profile.csv", index=False)
    return profile


def missing_value_summary(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for name, frame in tables.items():
        for column, count in frame.isna().sum().items():
            if count:
                rows.append(
                    {
                        "dataset": name,
                        "column": column,
                        "missing_count": int(count),
                        "missing_pct": count / len(frame),
                    }
                )
    summary = pd.DataFrame(rows, columns=["dataset", "column", "missing_count", "missing_pct"])
    summary.to_csv(OUTPUT_DIR / "missing_values.csv", index=False)
    return summary


def integrity_checks(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    trips = tables["trips"]
    checks = [
        ("trips.driver_id -> drivers.driver_id", trips["driver_id"], tables["drivers"]["driver_id"]),
        ("trips.vehicle_id -> vehicles.vehicle_id", trips["vehicle_id"], tables["vehicles"]["vehicle_id"]),
        ("trips.pickup_zone_id -> zones.zone_id", trips["pickup_zone_id"], tables["zones"]["zone_id"]),
        ("trips.drop_zone_id -> zones.zone_id", trips["drop_zone_id"], tables["zones"]["zone_id"]),
        ("vehicles.home_zone_id -> zones.zone_id", tables["vehicles"]["home_zone_id"], tables["zones"]["zone_id"]),
        ("drivers.home_zone_id -> zones.zone_id", tables["drivers"]["home_zone_id"], tables["zones"]["zone_id"]),
        ("events.zone_id -> zones.zone_id", tables["events"]["zone_id"], tables["zones"]["zone_id"]),
    ]
    rows = []
    for relationship, child, parent in checks:
        invalid = child.notna() & ~child.isin(parent.dropna())
        rows.append(
            {
                "relationship": relationship,
                "records_checked": len(child),
                "missing_foreign_keys": int(child.isna().sum()),
                "orphan_foreign_keys": int(invalid.sum()),
            }
        )
    result = pd.DataFrame(rows)
    result.to_csv(OUTPUT_DIR / "referential_integrity.csv", index=False)
    return result


def quality_checks(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    trips = tables["trips"]
    demand = tables["demand_supply"]
    traffic = tables["traffic"]
    rows = [
        ("trips", "non_positive_distance", int((trips["distance_km"] <= 0).sum())),
        ("trips", "non_positive_fare", int((trips["fare"] <= 0).sum())),
        ("trips", "negative_wait_time", int((trips["wait_time_min"] < 0).sum())),
        ("trips", "negative_duration", int((trips["trip_duration_min"] < 0).sum())),
        ("trips", "pickup_before_request", int((trips["pickup_timestamp"] < trips["request_timestamp"]).sum())),
        ("trips", "dropoff_before_pickup", int((trips["dropoff_timestamp"] < trips["pickup_timestamp"]).sum())),
        ("demand_supply", "negative_requests", int((demand["ride_requests"] < 0).sum())),
        ("demand_supply", "negative_available_vehicles", int((demand["available_vehicles"] < 0).sum())),
        ("demand_supply", "completed_plus_cancelled_exceeds_requests", int(((demand["completed_trips"] + demand["cancelled_trips"]) > demand["ride_requests"]).sum())),
        ("traffic", "non_positive_speed", int((traffic["avg_speed_kmph"] <= 0).sum())),
    ]
    result = pd.DataFrame(rows, columns=["dataset", "check", "failed_records"])
    result.to_csv(OUTPUT_DIR / "quality_checks.csv", index=False)
    return result


def business_metrics(tables: dict[str, pd.DataFrame]) -> tuple[dict[str, float], pd.DataFrame, pd.DataFrame]:
    trips = tables["trips"].copy()
    zones = tables["zones"][["zone_id", "city"]]
    completed = trips.loc[trips["status"].eq("Completed")].copy()
    pickup_city = trips.merge(zones, left_on="pickup_zone_id", right_on="zone_id", how="left")
    city_metrics = (
        pickup_city.groupby("city", dropna=False)
        .agg(trips=("trip_id", "size"), avg_wait_min=("wait_time_min", "mean"), avg_fare=("fare", "mean"))
        .reset_index()
    )
    vehicle_metrics = (
        trips.groupby("vehicle_type")
        .agg(trips=("trip_id", "size"), avg_fare=("fare", "mean"), avg_wait_min=("wait_time_min", "mean"))
        .reset_index()
    )
    city_metrics.to_csv(OUTPUT_DIR / "city_metrics.csv", index=False)
    vehicle_metrics.to_csv(OUTPUT_DIR / "vehicle_metrics.csv", index=False)
    demand = tables["demand_supply"]
    metrics = {
        "average_distance_km": float(trips["distance_km"].mean()),
        "average_fare_inr": float(trips["fare"].mean()),
        "average_wait_min": float(trips["wait_time_min"].mean()),
        "cancellation_rate": float(trips["status"].eq("Cancelled").mean()),
        "completed_revenue_inr": float(completed["fare"].sum()),
        "cross_city_trip_share": float((pickup_city["city"] != trips.merge(zones, left_on="drop_zone_id", right_on="zone_id", how="left")["city"]).mean()),
        "average_demand_supply_ratio": float((demand["ride_requests"] / demand["available_vehicles"].replace(0, np.nan)).mean()),
    }
    return metrics, city_metrics, vehicle_metrics


def markdown_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if max_rows is not None:
        frame = frame.head(max_rows)
    return frame.to_markdown(index=False)


def write_report(profile: pd.DataFrame, missing: pd.DataFrame, integrity: pd.DataFrame,
                 quality: pd.DataFrame, metrics: dict[str, float]) -> None:
    failed_quality = quality.loc[quality["failed_records"] > 0]
    integrity_failures = integrity.loc[(integrity["missing_foreign_keys"] > 0) | (integrity["orphan_foreign_keys"] > 0)]
    report = f"""# NCRMove Data Validation Report

Generated by `python/analysis/validate_data.py`. Raw source files are read-only and are synthetic.

## Dataset profile

{markdown_table(profile)}

## Referential integrity

{markdown_table(integrity)}

## Core quality checks

{markdown_table(quality)}

## Missing values

{markdown_table(missing, 30) if not missing.empty else 'No missing values found.'}

## Initial business metrics

| Metric | Value |
|---|---:|
| Average trip distance | {metrics['average_distance_km']:.2f} km |
| Average trip fare | ₹{metrics['average_fare_inr']:.2f} |
| Average customer wait | {metrics['average_wait_min']:.2f} min |
| Trip cancellation rate | {pct(metrics['cancellation_rate'])} |
| Completed-trip revenue | ₹{metrics['completed_revenue_inr']:,.2f} |
| Cross-city trip share | {pct(metrics['cross_city_trip_share'])} |
| Mean demand/supply ratio | {metrics['average_demand_supply_ratio']:.2f} |

## Validation outcome

* Referential-integrity failures: **{len(integrity_failures)}** relationships with missing or orphan keys.
* Failed core quality rules: **{len(failed_quality)}**.
* `trips_messy.csv` is deliberately excluded from clean-data KPIs and will be handled in the dedicated cleaning pipeline.
"""
    (OUTPUT_DIR / "validation_report.md").write_text(report, encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    tables = load_data()
    profile = write_data_profile(tables)
    missing = missing_value_summary(tables)
    integrity = integrity_checks(tables)
    quality = quality_checks(tables)
    metrics, _, _ = business_metrics(tables)
    write_report(profile, missing, integrity, quality, metrics)
    (OUTPUT_DIR / "kpis.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(f"Validation complete. Report: {OUTPUT_DIR / 'validation_report.md'}")


if __name__ == "__main__":
    main()

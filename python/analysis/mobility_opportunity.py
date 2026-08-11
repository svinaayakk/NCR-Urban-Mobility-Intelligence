"""Calculate NCRMove's transparent zone-hour Mobility Opportunity Score."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DATA = PROJECT_ROOT / "data" / "raw"
CLEANED_TRIPS = PROJECT_ROOT / "outputs" / "cleaning" / "trips_cleaned.csv"
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "mobility_opportunity"


def percentile_score(series: pd.Series) -> pd.Series:
    """Convert a numeric measure to an interpretable 0-100 percentile score."""
    return series.rank(pct=True, method="average").mul(100)


def classify(score: float) -> str:
    if score <= 25:
        return "Stable"
    if score <= 50:
        return "Monitor"
    if score <= 75:
        return "Intervention"
    return "Critical"


def main() -> None:
    if not CLEANED_TRIPS.exists():
        raise FileNotFoundError("Run python3 python/data_cleaning/clean_trips.py before calculating the score.")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    demand = pd.read_csv(RAW_DATA / "demand_supply.csv", parse_dates=["timestamp"])
    traffic = pd.read_csv(RAW_DATA / "traffic.csv", parse_dates=["timestamp"])
    weather = pd.read_csv(RAW_DATA / "weather.csv", parse_dates=["timestamp"])
    zones = pd.read_csv(RAW_DATA / "zones.csv")[["zone_id", "zone_name", "city"]]
    trips = pd.read_csv(CLEANED_TRIPS, parse_dates=["request_timestamp"])

    trips["completed_fare"] = trips["fare"].where(trips["status"].eq("Completed"), 0.0)
    trips["hour"] = trips["request_timestamp"].dt.hour
    hourly_trip_metrics = trips.groupby(["pickup_zone_id", "request_timestamp"]).agg(
        observed_trips=("trip_id", "size"),
        completed_revenue=("completed_fare", "sum"),
    ).reset_index().rename(columns={"pickup_zone_id": "zone_id", "request_timestamp": "timestamp"})
    # Use the full-year zone-and-hour mix, rather than a sparse single timestamp,
    # to recommend the category with the strongest recurring demand signal.
    vehicle_mix = trips.groupby(["pickup_zone_id", "hour", "vehicle_type"]).size().rename("vehicle_type_trips").reset_index()
    vehicle_mix = vehicle_mix.sort_values(
        ["pickup_zone_id", "hour", "vehicle_type_trips", "vehicle_type"],
        ascending=[True, True, False, True],
    ).drop_duplicates(["pickup_zone_id", "hour"])
    vehicle_mix = vehicle_mix.rename(columns={"pickup_zone_id": "zone_id", "vehicle_type": "recommended_vehicle_type"})

    score = demand.merge(zones, on="zone_id", how="left").merge(
        traffic[["timestamp", "zone_id", "traffic_index"]], on=["timestamp", "zone_id"], how="left"
    ).merge(weather[["timestamp", "rainfall_mm", "weather_condition"]], on="timestamp", how="left").merge(
        hourly_trip_metrics, on=["timestamp", "zone_id"], how="left"
    )
    score["hour"] = score["timestamp"].dt.hour
    score = score.merge(vehicle_mix[["zone_id", "hour", "recommended_vehicle_type"]], on=["zone_id", "hour"], how="left")

    score["observed_trips"] = score["observed_trips"].fillna(0).astype(int)
    score["completed_revenue"] = score["completed_revenue"].fillna(0.0)
    score["demand_supply_ratio"] = score["ride_requests"] / score["available_vehicles"].replace(0, np.nan)
    score["cancellation_rate"] = score["cancelled_trips"] / score["ride_requests"].replace(0, np.nan)
    score["supply_adequacy"] = score["available_vehicles"] / score["ride_requests"].replace(0, np.nan)

    score["demand_pressure_score"] = percentile_score(score["demand_supply_ratio"])
    score["cancellation_pressure_score"] = percentile_score(score["cancellation_rate"])
    score["wait_pressure_score"] = percentile_score(score["avg_wait_time_min"])
    score["revenue_opportunity_score"] = percentile_score(score["completed_revenue"])
    score["fleet_adequacy_score"] = percentile_score(score["supply_adequacy"])

    # Positive pressures total 90%; ample supply reduces the score by up to 10%.
    score["mobility_opportunity_score"] = (
        0.30 * score["demand_pressure_score"]
        + 0.20 * score["cancellation_pressure_score"]
        + 0.20 * score["wait_pressure_score"]
        + 0.20 * score["revenue_opportunity_score"]
        - 0.10 * score["fleet_adequacy_score"]
    ).div(0.80).clip(0, 100).round(1)
    score["priority_band"] = score["mobility_opportunity_score"].map(classify)
    score["recommended_vehicle_type"] = score["recommended_vehicle_type"].fillna("Review demand mix")

    columns = [
        "timestamp", "hour", "city", "zone_id", "zone_name", "ride_requests", "available_vehicles",
        "demand_supply_ratio", "cancelled_trips", "cancellation_rate", "avg_wait_time_min", "traffic_index",
        "rainfall_mm", "weather_condition", "completed_revenue", "recommended_vehicle_type",
        "demand_pressure_score", "cancellation_pressure_score", "wait_pressure_score",
        "revenue_opportunity_score", "fleet_adequacy_score", "mobility_opportunity_score", "priority_band",
    ]
    score[columns].to_csv(OUTPUT_DIR / "zone_hour_opportunity_scores.csv", index=False)

    recommendations = score.groupby(["city", "zone_id", "zone_name", "hour", "recommended_vehicle_type"]).agg(
        avg_opportunity_score=("mobility_opportunity_score", "mean"),
        critical_hours=("priority_band", lambda values: (values == "Critical").sum()),
        avg_demand_supply_ratio=("demand_supply_ratio", "mean"),
        avg_wait_time_min=("avg_wait_time_min", "mean"),
        avg_cancellation_rate=("cancellation_rate", "mean"),
        avg_completed_revenue=("completed_revenue", "mean"),
    ).reset_index()
    recommendations = recommendations.sort_values(
        ["avg_opportunity_score", "critical_hours"], ascending=False
    )
    recommendations["recommended_action"] = np.where(
        recommendations["avg_opportunity_score"] > 75,
        "Prioritize additional fleet or reposition vehicles into this zone-hour.",
        "Monitor demand and reposition fleet if pressure persists.",
    )
    recommendations.to_csv(OUTPUT_DIR / "zone_hour_fleet_recommendations.csv", index=False)

    top = recommendations.head(20).copy()
    report = f"""# NCRMove Mobility Opportunity Score

The score identifies zone-hours where fleet intervention is most valuable. It is a transparent prioritization tool, not a black-box prediction.

## Formula

All five input measures are converted to percentile scores from 0–100 across the 490,560 zone-hours.

```text
Mobility Opportunity Score =
(30% × demand pressure)
+ (20% × cancellation pressure)
+ (20% × wait pressure)
+ (20% × completed-revenue opportunity)
- (10% × fleet adequacy)
then rescaled to 0–100
```

Fleet adequacy is a penalty: a zone-hour with relatively abundant available vehicles is less urgent, all else equal.

## Priority bands

| Score | Band | Meaning |
|---:|---|---|
| 0–25 | Stable | Normal operations |
| 26–50 | Monitor | Watch for sustained pressure |
| 51–75 | Intervention | Evaluate fleet reallocation |
| 76–100 | Critical | Prioritize targeted fleet action |

## Top recurring fleet-allocation opportunities

{top.to_markdown(index=False, floatfmt='.2f')}

## Interpretation safeguard

`recommended_vehicle_type` is the most frequently requested trip category for that zone-hour. It is a demand-mix signal, not proof that a vehicle should be purchased. Recommendations should be tested with capacity, driver availability, and repositioning constraints before deployment.
"""
    (OUTPUT_DIR / "mobility_opportunity_methodology.md").write_text(report, encoding="utf-8")
    print(f"Opportunity score complete. Top recommendation: {top.iloc[0]['zone_name']} at {int(top.iloc[0]['hour']):02d}:00")


if __name__ == "__main__":
    main()

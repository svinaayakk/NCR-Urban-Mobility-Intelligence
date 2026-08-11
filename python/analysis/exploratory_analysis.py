"""Create reproducible exploratory analysis outputs for the NCRMove project."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DATA = PROJECT_ROOT / "data" / "raw"
CLEANED_TRIPS = PROJECT_ROOT / "outputs" / "cleaning" / "trips_cleaned.csv"
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "eda"

CITY_ORDER = ["Noida", "Delhi", "Gurugram"]
CITY_PALETTE = {"Noida": "#25A18E", "Delhi": "#445E93", "Gurugram": "#D97706"}


def save_plot(fig: plt.Figure, name: str) -> None:
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / name, dpi=180, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    if not CLEANED_TRIPS.exists():
        raise FileNotFoundError("Cleaned trips are missing. Run python3 python/data_cleaning/clean_trips.py first.")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    sns.set_theme(style="whitegrid", font_scale=0.9)
    trips = pd.read_csv(CLEANED_TRIPS, parse_dates=["request_timestamp"])
    zones = pd.read_csv(RAW_DATA / "zones.csv")[["zone_id", "zone_name", "city"]]
    trips = trips.merge(
        zones.rename(columns={"zone_id": "pickup_zone_id", "zone_name": "pickup_zone_name", "city": "pickup_city"}),
        on="pickup_zone_id", how="left",
    ).merge(zones.rename(columns={"zone_id": "drop_zone_id", "city": "drop_city"}), on="drop_zone_id", how="left")
    trips["hour"] = trips["request_timestamp"].dt.hour
    trips["is_cancelled"] = trips["status"].eq("Cancelled")
    trips["is_cross_city"] = trips["pickup_city"].ne(trips["drop_city"])
    trips["completed_fare"] = trips["fare"].where(trips["status"].eq("Completed"), 0)

    hourly = trips.groupby("hour").agg(trips=("trip_id", "size"), avg_wait_min=("wait_time_min", "mean")).reset_index()
    city = trips.groupby("pickup_city").agg(trips=("trip_id", "size"), cancellation_rate=("is_cancelled", "mean"), avg_wait_min=("wait_time_min", "mean"), completed_revenue=("completed_fare", "sum")).reindex(CITY_ORDER).reset_index()
    vehicle = trips.groupby("vehicle_type").agg(trips=("trip_id", "size"), completed_revenue=("completed_fare", "sum"), avg_fare=("fare", "mean")).sort_values("completed_revenue", ascending=False).reset_index()
    zone_metrics = trips.groupby(["pickup_zone_id", "pickup_zone_name", "pickup_city"]).agg(trips=("trip_id", "size"), cancellation_rate=("is_cancelled", "mean"), avg_wait_min=("wait_time_min", "mean"), completed_revenue=("completed_fare", "sum")).reset_index().sort_values("trips", ascending=False)
    corridors = trips.loc[trips["is_cross_city"]].groupby(["pickup_city", "drop_city"]).agg(trips=("trip_id", "size"), avg_wait_min=("wait_time_min", "mean"), completed_revenue=("completed_fare", "sum")).reset_index().sort_values("trips", ascending=False)
    hourly.to_csv(OUTPUT_DIR / "hourly_metrics.csv", index=False)
    city.to_csv(OUTPUT_DIR / "city_metrics.csv", index=False)
    vehicle.to_csv(OUTPUT_DIR / "vehicle_metrics.csv", index=False)
    zone_metrics.to_csv(OUTPUT_DIR / "zone_metrics.csv", index=False)
    corridors.to_csv(OUTPUT_DIR / "cross_city_corridors.csv", index=False)

    fig, axes = plt.subplots(2, 3, figsize=(16, 9))
    axes[0, 0].plot(hourly["hour"], hourly["trips"], color="#445E93", linewidth=2.5)
    axes[0, 0].set(title="Trip demand by hour", xlabel="Hour of day", ylabel="Trips")
    axes[0, 0].set_xticks(range(0, 24, 2))
    sns.barplot(data=city, x="pickup_city", y="trips", hue="pickup_city", palette=CITY_PALETTE, legend=False, ax=axes[0, 1])
    axes[0, 1].set(title="Trips by pickup city", xlabel="", ylabel="Trips")
    city_cancel = city.assign(cancellation_pct=city["cancellation_rate"] * 100)
    sns.barplot(data=city_cancel, x="pickup_city", y="cancellation_pct", hue="pickup_city", palette=CITY_PALETTE, legend=False, ax=axes[0, 2])
    axes[0, 2].set(title="Cancellation rate by city", xlabel="", ylabel="Cancellation rate (%)")
    axes[1, 0].plot(hourly["hour"], hourly["avg_wait_min"], color="#D97706", linewidth=2.5)
    axes[1, 0].set(title="Average wait by hour", xlabel="Hour of day", ylabel="Minutes")
    axes[1, 0].set_xticks(range(0, 24, 2))
    sns.barplot(data=vehicle, x="completed_revenue", y="vehicle_type", color="#25A18E", ax=axes[1, 1])
    axes[1, 1].set(title="Completed-trip revenue by vehicle", xlabel="Revenue (INR)", ylabel="")
    axes[1, 1].ticklabel_format(style="plain", axis="x")
    top_corridors = corridors.head(6).copy()
    top_corridors["corridor"] = top_corridors["pickup_city"] + " → " + top_corridors["drop_city"]
    sns.barplot(data=top_corridors, x="trips", y="corridor", color="#8B5CF6", ax=axes[1, 2])
    axes[1, 2].set(title="Top cross-city corridors", xlabel="Trips", ylabel="")
    save_plot(fig, "mobility_eda_dashboard.png")

    top_demand = zone_metrics.head(5)[["pickup_zone_name", "pickup_city", "trips"]]
    worst_wait = zone_metrics.nlargest(5, "avg_wait_min")[["pickup_zone_name", "pickup_city", "avg_wait_min"]]
    highest_cancel = zone_metrics.nlargest(5, "cancellation_rate")[["pickup_zone_name", "pickup_city", "cancellation_rate"]].copy()
    highest_cancel["cancellation_rate"] *= 100
    peak_hour = hourly.loc[hourly["trips"].idxmax()]
    highest_revenue_vehicle = vehicle.iloc[0]
    report = f"""# NCRMove Exploratory Analysis

This analysis uses the cleaned synthetic trip extract: **{len(trips):,} trips**.

## Headline findings

* **Peak demand hour:** {int(peak_hour['hour']):02d}:00 with **{int(peak_hour['trips']):,}** requests.
* **Largest pickup market:** **{city.loc[city['trips'].idxmax(), 'pickup_city']}** with **{int(city['trips'].max()):,}** trips.
* **Highest completed-trip revenue vehicle type:** **{highest_revenue_vehicle['vehicle_type']}** at **₹{highest_revenue_vehicle['completed_revenue']:,.0f}**.
* **Cross-city trips:** **{trips['is_cross_city'].mean():.2%}** of cleaned trips.

## Highest-demand pickup zones

{top_demand.to_markdown(index=False)}

## Zones with the longest average waits

{worst_wait.to_markdown(index=False, floatfmt='.2f')}

## Zones with the highest cancellation rates

{highest_cancel.to_markdown(index=False, floatfmt='.2f')}

## Files produced

* `mobility_eda_dashboard.png` — six-chart EDA overview.
* `zone_metrics.csv` — zone-level analytical table for the later Mobility Opportunity Score.
* `cross_city_corridors.csv` — inter-city corridor analysis.

These are descriptive findings only. Fleet allocation recommendations will be made after combining demand-supply, traffic, weather, and utilization measures.
"""
    (OUTPUT_DIR / "eda_findings.md").write_text(report, encoding="utf-8")
    print(f"EDA complete. Dashboard: {OUTPUT_DIR / 'mobility_eda_dashboard.png'}")


if __name__ == "__main__":
    main()

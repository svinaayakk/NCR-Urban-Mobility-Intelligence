"""Create Spark fleet-pressure and revenue aggregations for NCRMove."""

from __future__ import annotations

import argparse
from pathlib import Path

from pyspark.sql import SparkSession, functions as F


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Aggregate NCRMove data with PySpark.")
    parser.add_argument("--raw-data", default=str(PROJECT_ROOT / "data" / "raw"))
    parser.add_argument("--output-dir", default=str(PROJECT_ROOT / "outputs" / "spark"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    spark = SparkSession.builder.appName("NCRMoveMobilityAggregation").getOrCreate()
    spark.sparkContext.setLogLevel("WARN")
    raw = args.raw_data.rstrip("/")
    output = args.output_dir.rstrip("/")

    zones = spark.read.option("header", True).option("inferSchema", True).csv(f"{raw}/zones.csv")
    demand = spark.read.option("header", True).option("inferSchema", True).csv(f"{raw}/demand_supply.csv").withColumn("timestamp", F.to_timestamp("timestamp"))
    traffic = spark.read.option("header", True).option("inferSchema", True).csv(f"{raw}/traffic.csv").withColumn("timestamp", F.to_timestamp("timestamp"))
    trips = spark.read.parquet(f"{output}/trips_cleaned")

    hourly_revenue = (
        trips.withColumn("hour_timestamp", F.date_trunc("hour", "request_timestamp"))
        .groupBy(F.col("pickup_zone_id").alias("zone_id"), F.col("hour_timestamp").alias("timestamp"))
        .agg(
            F.count("trip_id").alias("observed_trips"),
            F.sum(F.when(F.col("status") == "Completed", F.col("fare")).otherwise(F.lit(0.0))).alias("completed_revenue"),
        )
    )

    fleet_pressure = (
        demand.join(zones.select("zone_id", "zone_name", "city"), "zone_id")
        .join(traffic.select("timestamp", "zone_id", "traffic_index"), ["timestamp", "zone_id"], "left")
        .join(hourly_revenue, ["timestamp", "zone_id"], "left")
        .withColumn("demand_supply_ratio", F.round(F.col("ride_requests") / F.when(F.col("available_vehicles") > 0, F.col("available_vehicles")), 2))
        .fillna({"observed_trips": 0, "completed_revenue": 0.0})
    )
    fleet_pressure.write.mode("overwrite").parquet(f"{output}/fleet_pressure")

    vehicle_revenue = (
        trips.groupBy("vehicle_type")
        .agg(
            F.count("trip_id").alias("trips"),
            F.round(F.sum(F.when(F.col("status") == "Completed", F.col("fare")).otherwise(F.lit(0.0))), 2).alias("completed_revenue"),
            F.round(F.avg("fare"), 2).alias("avg_fare"),
        )
        .orderBy(F.desc("completed_revenue"))
    )
    vehicle_revenue.write.mode("overwrite").parquet(f"{output}/vehicle_revenue")
    vehicle_revenue.show(truncate=False)
    spark.stop()


if __name__ == "__main__":
    main()

"""Clean the NCRMove messy trip extract with PySpark and write Parquet output.

Example local run:
    spark-submit pyspark/trip_processing.py

Example Databricks adaptation:
    python trip_processing.py --raw-data /Volumes/catalog/schema/ncrmove/raw \
      --output-dir /Volumes/catalog/schema/ncrmove/processed
"""

from __future__ import annotations

import argparse
from pathlib import Path

from pyspark.sql import SparkSession, functions as F


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Clean NCRMove trips with PySpark.")
    parser.add_argument("--raw-data", default=str(PROJECT_ROOT / "data" / "raw"))
    parser.add_argument("--output-dir", default=str(PROJECT_ROOT / "outputs" / "spark"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    spark = SparkSession.builder.appName("NCRMoveTripProcessing").getOrCreate()
    spark.sparkContext.setLogLevel("WARN")

    source = f"{args.raw_data.rstrip('/')}/trips_messy.csv"
    output = f"{args.output_dir.rstrip('/')}/trips_cleaned"
    trips = spark.read.option("header", True).option("inferSchema", True).csv(source)
    source_count = trips.count()

    cleaned = (
        trips.dropDuplicates()
        .filter((F.col("distance_km") > 0) & (F.col("fare") > 0))
        .withColumn("payment_method", F.when(F.col("payment_method") == "upi", F.lit("UPI")).otherwise(F.col("payment_method")))
        .withColumn("discount", F.coalesce(F.col("discount"), F.lit(0.0)))
        .withColumn("is_driver_linked", F.col("driver_id").isNotNull())
        .withColumn("request_timestamp", F.to_timestamp("request_timestamp"))
        .withColumn("pickup_timestamp", F.to_timestamp("pickup_timestamp"))
        .withColumn("dropoff_timestamp", F.to_timestamp("dropoff_timestamp"))
    )
    cleaned.write.mode("overwrite").parquet(output)
    cleaned_count = cleaned.count()
    print(f"Source rows: {source_count:,}; cleaned Spark rows: {cleaned_count:,}; output: {output}")
    spark.stop()


if __name__ == "__main__":
    main()

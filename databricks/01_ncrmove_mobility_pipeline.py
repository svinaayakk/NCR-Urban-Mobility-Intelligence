# Databricks notebook source
# MAGIC %md
# MAGIC # NCRMove Mobility Pipeline
# MAGIC
# MAGIC This notebook processes synthetic NCRMove raw CSVs into Delta tables for analysis.
# MAGIC Configure the three widgets below to match your Unity Catalog volume paths.

# COMMAND ----------

dbutils.widgets.text("raw_data_path", "/Volumes/<catalog>/<schema>/ncrmove/raw")
dbutils.widgets.text("processed_data_path", "/Volumes/<catalog>/<schema>/ncrmove/processed")
dbutils.widgets.text("table_prefix", "ncrmove")

raw_data_path = dbutils.widgets.get("raw_data_path").rstrip("/")
processed_data_path = dbutils.widgets.get("processed_data_path").rstrip("/")
table_prefix = dbutils.widgets.get("table_prefix")

# COMMAND ----------

from pyspark.sql import functions as F

trips_messy = spark.read.option("header", True).option("inferSchema", True).csv(
    f"{raw_data_path}/trips_messy.csv"
)
zones = spark.read.option("header", True).option("inferSchema", True).csv(f"{raw_data_path}/zones.csv")
demand_supply = (
    spark.read.option("header", True).option("inferSchema", True)
    .csv(f"{raw_data_path}/demand_supply.csv")
    .withColumn("timestamp", F.to_timestamp("timestamp"))
)
traffic = (
    spark.read.option("header", True).option("inferSchema", True)
    .csv(f"{raw_data_path}/traffic.csv")
    .withColumn("timestamp", F.to_timestamp("timestamp"))
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Clean trips
# MAGIC
# MAGIC Rules match the local Python/PySpark pipeline: remove exact duplicates and impossible fares/distances, normalize UPI, impute missing discounts with zero, and flag unknown drivers.

# COMMAND ----------

trips_cleaned = (
    trips_messy.dropDuplicates()
    .filter((F.col("distance_km") > 0) & (F.col("fare") > 0))
    .withColumn("payment_method", F.when(F.col("payment_method") == "upi", F.lit("UPI")).otherwise(F.col("payment_method")))
    .withColumn("discount", F.coalesce(F.col("discount"), F.lit(0.0)))
    .withColumn("is_driver_linked", F.col("driver_id").isNotNull())
    .withColumn("request_timestamp", F.to_timestamp("request_timestamp"))
    .withColumn("pickup_timestamp", F.to_timestamp("pickup_timestamp"))
    .withColumn("dropoff_timestamp", F.to_timestamp("dropoff_timestamp"))
)

trips_cleaned.write.format("delta").mode("overwrite").saveAsTable(f"{table_prefix}_trips_cleaned")
trips_cleaned.write.format("delta").mode("overwrite").save(f"{processed_data_path}/trips_cleaned")
display(trips_cleaned.limit(10))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Build hourly fleet-pressure table

# COMMAND ----------

hourly_revenue = (
    trips_cleaned.withColumn("hour_timestamp", F.date_trunc("hour", "request_timestamp"))
    .groupBy(F.col("pickup_zone_id").alias("zone_id"), F.col("hour_timestamp").alias("timestamp"))
    .agg(
        F.count("trip_id").alias("observed_trips"),
        F.sum(F.when(F.col("status") == "Completed", F.col("fare")).otherwise(F.lit(0.0))).alias("completed_revenue"),
    )
)

fleet_pressure = (
    demand_supply.join(zones.select("zone_id", "zone_name", "city"), "zone_id")
    .join(traffic.select("timestamp", "zone_id", "traffic_index"), ["timestamp", "zone_id"], "left")
    .join(hourly_revenue, ["timestamp", "zone_id"], "left")
    .withColumn("demand_supply_ratio", F.round(F.col("ride_requests") / F.when(F.col("available_vehicles") > 0, F.col("available_vehicles")), 2))
    .fillna({"observed_trips": 0, "completed_revenue": 0.0})
)

fleet_pressure.write.format("delta").mode("overwrite").saveAsTable(f"{table_prefix}_fleet_pressure")
fleet_pressure.write.format("delta").mode("overwrite").save(f"{processed_data_path}/fleet_pressure")
display(fleet_pressure.orderBy(F.desc("demand_supply_ratio")).limit(20))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Data-quality and reconciliation checks

# COMMAND ----------

print(f"Cleaned trips: {trips_cleaned.count():,}")
print(f"Fleet-pressure rows: {fleet_pressure.count():,}")
assert trips_cleaned.filter((F.col("distance_km") <= 0) | (F.col("fare") <= 0)).count() == 0
assert fleet_pressure.filter(F.col("demand_supply_ratio").isNull()).count() == 0

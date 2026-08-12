# NCR Mobility Intelligence & Fleet Optimization

NCRMove is a synthetic multi-modal ride-hailing analytics case study covering 56 analytical zones across Noida, Delhi and Gurugram in 2026.

## Data layout

Raw source files are available at `data/raw/`. This project currently uses a local symbolic link to the supplied dataset; raw files are not modified by the pipeline.

## Run validation

```bash
python3 python/analysis/validate_data.py
```

The command writes a Markdown report and CSV summaries to `outputs/validation/`.

## Run cleaning and exploratory analysis

```bash
python3 python/data_cleaning/clean_trips.py
python3 python/analysis/exploratory_analysis.py
```

The EDA command creates a chart dashboard, zone-level metrics, and a findings summary in `outputs/eda/`.

## Run SQL analysis

```bash
python3 python/database/load_sqlite.py
python3 python/database/run_sql_analysis.py
```

This creates a local SQLite analytical database and exports the business-query results to `outputs/sql/`.

## Calculate fleet-allocation opportunities

```bash
python3 python/analysis/mobility_opportunity.py
```

This produces a transparent 0–100 Mobility Opportunity Score for each zone-hour, including priority bands and recommended vehicle type based on observed demand mix.

## Run PySpark processing

```bash
spark-submit pyspark/trip_processing.py
spark-submit pyspark/mobility_aggregation.py
```

The scripts create Spark/Parquet equivalents of the cleaning and fleet-pressure transformations. For Databricks, upload the raw CSV files and run the same scripts with `--raw-data` and `--output-dir` paths appropriate to DBFS or a Unity Catalog volume.

## Databricks notebook

Import `databricks/01_ncrmove_mobility_pipeline.py` into a Databricks workspace. The notebook writes cleaned trips and fleet-pressure outputs as Delta tables; see `docs/databricks_setup.md` for the required path configuration.

The data is synthetic and must not be represented as Uber, Ola, or measured NCR ride-hailing data.

# Databricks Setup — NCRMove

This project includes an import-ready Databricks source notebook: `databricks/01_ncrmove_mobility_pipeline.py`.

## One-time setup

1. Create or choose a Databricks workspace with a Unity Catalog-enabled compute cluster.
2. Upload these synthetic raw CSV files to a Unity Catalog volume or another approved storage location:
   `zones.csv`, `demand_supply.csv`, `traffic.csv`, and `trips_messy.csv`.
3. In Databricks Workspace, select **Import** and import `01_ncrmove_mobility_pipeline.py` as a notebook.
4. Attach the notebook to a running cluster.
5. Update the notebook widgets:
   - `raw_data_path`: folder containing the uploaded CSVs
   - `processed_data_path`: folder where Delta output can be written
   - `table_prefix`: a simple prefix such as `ncrmove`

## Outputs

The notebook creates two Delta tables:

* `<table_prefix>_trips_cleaned`
* `<table_prefix>_fleet_pressure`

It also writes the same data to Delta folders under `processed_data_path`. These tables are the Databricks equivalents of the local Python cleaning and Spark aggregation outputs.

## Validation

The final cell verifies that cleaned trips have no non-positive fare/distance records and displays the highest fleet-pressure zone-hours.

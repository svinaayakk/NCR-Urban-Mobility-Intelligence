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

The data is synthetic and must not be represented as Uber, Ola, or measured NCR ride-hailing data.

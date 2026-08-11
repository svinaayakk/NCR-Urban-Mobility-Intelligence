"""Clean the intentionally flawed NCRMove trip extract with an auditable rule set.

The raw file is never changed. The cleaned output preserves trips with an unknown
driver for customer/demand analysis, but flags them so they can be excluded from
driver-level analysis.
"""

from __future__ import annotations

from pathlib import Path
import json

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE = PROJECT_ROOT / "data" / "raw" / "trips_messy.csv"
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "cleaning"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    trips = pd.read_csv(
        SOURCE,
        parse_dates=["request_timestamp", "pickup_timestamp", "dropoff_timestamp"],
    )
    audit: list[dict[str, object]] = []
    initial_rows = len(trips)

    duplicate_rows = int(trips.duplicated().sum())
    trips = trips.drop_duplicates().copy()
    audit.append({
        "step": "Remove exact duplicate rows",
        "action": "Dropped duplicate records after retaining the first occurrence.",
        "affected_records": duplicate_rows,
        "rows_remaining": len(trips),
    })

    invalid_trip = (trips["distance_km"] <= 0) | (trips["fare"] <= 0)
    invalid_count = int(invalid_trip.sum())
    trips = trips.loc[~invalid_trip].copy()
    audit.append({
        "step": "Remove invalid fare or distance",
        "action": "Dropped records with distance_km <= 0 or fare <= 0; neither value can be inferred reliably.",
        "affected_records": invalid_count,
        "rows_remaining": len(trips),
    })

    lowercase_upi = int(trips["payment_method"].eq("upi").sum())
    trips["payment_method"] = trips["payment_method"].replace({"upi": "UPI"})
    audit.append({
        "step": "Standardize payment method labels",
        "action": "Converted lowercase 'upi' to the canonical category 'UPI'.",
        "affected_records": lowercase_upi,
        "rows_remaining": len(trips),
    })

    missing_discount = int(trips["discount"].isna().sum())
    trips["discount"] = trips["discount"].fillna(0.0)
    audit.append({
        "step": "Impute missing discounts",
        "action": "Filled missing discount with 0.0 because discounts are monetary adjustments and no discount is the conservative default.",
        "affected_records": missing_discount,
        "rows_remaining": len(trips),
    })

    missing_driver = int(trips["driver_id"].isna().sum())
    trips["is_driver_linked"] = trips["driver_id"].notna()
    audit.append({
        "step": "Flag unknown drivers",
        "action": "Retained trips with a missing driver_id for demand/customer analysis and added is_driver_linked; exclude these rows from driver-level analysis.",
        "affected_records": missing_driver,
        "rows_remaining": len(trips),
    })

    audit_frame = pd.DataFrame(audit)
    audit_frame.to_csv(OUTPUT_DIR / "cleaning_audit.csv", index=False)
    trips.to_csv(OUTPUT_DIR / "trips_cleaned.csv", index=False)

    summary = {
        "source_rows": initial_rows,
        "cleaned_rows": len(trips),
        "duplicate_rows_removed": duplicate_rows,
        "invalid_fare_or_distance_rows_removed": invalid_count,
        "payment_labels_standardized": lowercase_upi,
        "missing_discounts_imputed": missing_discount,
        "trips_without_driver_id_flagged": missing_driver,
        "unrated_trips_retained": int(trips["rating"].isna().sum()),
        "null_cancellation_reasons_retained": int(trips["cancellation_reason"].isna().sum()),
    }
    (OUTPUT_DIR / "cleaning_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    report = f"""# NCRMove Trip Cleaning Report

Source: `trips_messy.csv` (synthetic and intentionally flawed). The raw file was not changed.

## Cleaning rules and audit

{audit_frame.to_markdown(index=False)}

## Outcome

* Source rows: **{initial_rows:,}**
* Analysis-ready rows: **{len(trips):,}**
* Removed rows: **{initial_rows - len(trips):,}**
* Remaining records with an unlinked driver: **{missing_driver:,}** — retained only for non-driver analyses.
* Missing ratings remain null because a rating cannot be inferred credibly.
* Null cancellation reasons remain null; they are expected for non-cancelled trips.

## Output use

Use `trips_cleaned.csv` for trip, demand, revenue, cancellation, and customer-experience analysis. Filter `is_driver_linked == True` for driver performance or driver-utilization analysis.
"""
    (OUTPUT_DIR / "cleaning_report.md").write_text(report, encoding="utf-8")
    print(f"Cleaning complete. Report: {OUTPUT_DIR / 'cleaning_report.md'}")


if __name__ == "__main__":
    main()

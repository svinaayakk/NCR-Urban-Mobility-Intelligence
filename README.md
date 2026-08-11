# NCR Mobility Intelligence & Fleet Optimization

NCRMove is a synthetic multi-modal ride-hailing analytics case study covering 56 analytical zones across Noida, Delhi and Gurugram in 2026.

## Data layout

Raw source files are available at `data/raw/`. This project currently uses a local symbolic link to the supplied dataset; raw files are not modified by the pipeline.

## Run validation

```bash
python3 python/analysis/validate_data.py
```

The command writes a Markdown report and CSV summaries to `outputs/validation/`.

The data is synthetic and must not be represented as Uber, Ola, or measured NCR ride-hailing data.

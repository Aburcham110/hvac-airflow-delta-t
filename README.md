# HVAC Airflow / ΔT Helper (Educational)

Python **stdlib-only** CLI for measured temperature split (ΔT), typical educational bands, optional rough CFM, and a ranked “check next” tree.

> **Educational only — not Manual D.**  
> Not a substitute for anemometer airflow measurement or OEM temperature-rise / CFM charts.

## Quick start

```bash
cd hvac-airflow-delta-t
python3 airflow_delta_t.py --help
python3 airflow_delta_t.py -i
```

### Residential cooling example

```bash
python3 airflow_delta_t.py \
  --system res-ac \
  --supply 55 --return-temp 75
```

### Furnace with nameplate-ish heat for rough CFM

```bash
python3 airflow_delta_t.py \
  --system furnace \
  --supply 120 --return-temp 70 \
  --btu 80000
```

## System types

`res-ac` · `hp-cool` · `hp-heat` · `furnace` · `commercial-rtu`

Rough CFM uses BTUh ≈ 1.08 × CFM × |ΔT| when `--kw` or `--btu` is given.

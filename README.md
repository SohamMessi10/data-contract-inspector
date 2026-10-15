# Data Contract Inspector

Check a CSV against an agreed **data contract** before it enters an analysis or pipeline,
and get a readable explanation of every missing column, invalid value, and duplicate ID.

> **Status:** in development. The contract format and contract loader are done; checking
> CSV files against a contract is the next milestone. See [`PROGRESS.md`](PROGRESS.md).

## Why

Analysts often discover bad data only after a chart looks wrong. Tools that silently
coerce values (`"1,000"` → `NaN`, `"three"` → dropped row) hide the problem instead of
reporting it. This tool makes the expectations explicit in a contract file and reports
violations without changing the data.

## Setup

Requires Python 3.11+.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m pytest
```

## Contract format

See [`docs/contract-spec.md`](docs/contract-spec.md) for the full format, how CSV values
are interpreted, exit codes, and the acceptance fixture. Example:
[`examples/orders.contract.json`](examples/orders.contract.json).

All data in `examples/` is synthetic.

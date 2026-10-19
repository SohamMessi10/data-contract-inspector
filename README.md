# Data Contract Inspector

[![tests](https://github.com/SohamMessi10/data-contract-inspector/actions/workflows/tests.yml/badge.svg)](https://github.com/SohamMessi10/data-contract-inspector/actions/workflows/tests.yml)

Check a CSV against an agreed **data contract** before it enters an analysis or pipeline,
and get a readable explanation of every missing column, invalid value, and duplicate ID.

> **Status:** in development. The checks, the command-line tool, and CI work; a full demo
> write-up is next. See [`PROGRESS.md`](PROGRESS.md).

## Why

Analysts often discover bad data only after a chart looks wrong. Tools that silently
coerce values (`"1,000"` → `NaN`, `"three"` → dropped row) hide the problem instead of
reporting it. This tool makes the expectations explicit in a contract file and reports
violations without changing the data.

## Setup

Requires Python 3.11+. CI tests Python 3.11–3.14 on Linux and 3.13 on macOS.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m pytest
```

## Usage

```bash
contract-inspector check examples/orders_invalid.csv --contract examples/orders.contract.json
```

```
FAIL: examples/orders_invalid.csv against contract 'orders'
6 rows checked, 0 skipped, 5 errors, 0 warnings

  error    line 3 [quantity]: '0' is below the minimum of 1
  error    line 4 [customer_email]: value is null; column allows no nulls (1 of 6 rows null)
  error    line 5 [order_id]: '1003' duplicates the primary key on line 4
  error    line 6 [quantity]: 'three' is not an integer
  error    line 7 [unit_price]: '-2.00' is below the minimum of 0
```

Add `--report out.json` to save the full JSON report, or `--json` to print it instead of the
summary. The exit code (0 pass, 1 violations, 2 usage or contract error, 3 unreadable dataset,
4 report not written) lets scripts and CI act on the result without parsing text.

## Contract format

See [`docs/contract-spec.md`](docs/contract-spec.md) for the full format, how CSV values
are interpreted, exit codes, and the acceptance fixture. Example:
[`examples/orders.contract.json`](examples/orders.contract.json).

All data in `examples/` is synthetic.

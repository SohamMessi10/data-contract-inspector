# Data Contract Inspector

[![tests](https://github.com/SohamMessi10/data-contract-inspector/actions/workflows/tests.yml/badge.svg)](https://github.com/SohamMessi10/data-contract-inspector/actions/workflows/tests.yml)

A command-line tool that checks a CSV file against an agreed **data contract** before the data
enters an analysis or pipeline. It reports every missing column, invalid value, and duplicate
ID with its line number, and it never changes the data.

## The problem

Bad data is usually found late, when a chart looks wrong or a model behaves oddly. A common
cause is **silent coercion**: a conversion step quietly turns a bad value into something that
looks valid. Python's own conversions are more forgiving than most people expect:

```python
>>> float("1_000"), float(" 5 "), float("1e3"), float("nan")
(1000.0, 5.0, 1000.0, nan)
>>> int(" 7 ")
7
```

A pipeline built on these conversions accepts typos and formatting accidents as real numbers,
and a `NaN` slips through every `<` or `>` comparison because they are all false. Spreadsheet
and dataframe tools add their own guesses on top: blank-as-zero, values coerced to missing,
rows dropped.

This tool takes the opposite approach. You write the expectations down once in a small JSON
contract. The tool checks the raw text against it and **reports** anything that does not match,
so a person decides what to fix.

## Demo

All data in [`examples/`](examples/) is synthetic: fictional orders with `example.com` addresses.

**The contract** ([`examples/orders.contract.json`](examples/orders.contract.json)):

```json
{
  "contract_version": 1,
  "name": "orders",
  "primary_key": "order_id",
  "columns": [
    {"name": "order_id", "type": "integer"},
    {"name": "customer_email", "type": "string"},
    {"name": "quantity", "type": "integer", "min": 1, "max": 1000},
    {"name": "unit_price", "type": "number", "min": 0},
    {"name": "coupon_code", "type": "string", "required": false, "max_null_fraction": 1.0}
  ]
}
```

**A broken file** ([`examples/orders_invalid.csv`](examples/orders_invalid.csv)):

```
order_id,customer_email,quantity,unit_price,coupon_code
1001,ana@example.com,2,19.99,
1002,ben@example.com,0,5.00,SAVE10
1003,,1,12.50,
1003,dee@example.com,3,8.00,
1005,eli@example.com,three,4.25,WELCOME
1006,fay@example.com,1,-2.00,
```

```console
$ contract-inspector check examples/orders_invalid.csv --contract examples/orders.contract.json
FAIL: examples/orders_invalid.csv against contract 'orders'
6 rows checked, 0 skipped, 5 errors, 0 warnings

  error    line 3 [quantity]: '0' is below the minimum of 1
  error    line 4 [customer_email]: value is null; column allows no nulls (1 of 6 rows null)
  error    line 5 [order_id]: '1003' duplicates the primary key on line 4
  error    line 6 [quantity]: 'three' is not an integer
  error    line 7 [unit_price]: '-2.00' is below the minimum of 0
$ echo $?
1
```

Each finding names the line, the column, and what is wrong, so it can be fixed directly.
The same findings as JSON, for other programs, are in
[`examples/orders_invalid.report.json`](examples/orders_invalid.report.json).

**A file that meets the contract** ([`examples/orders_valid.csv`](examples/orders_valid.csv)):

```console
$ contract-inspector check examples/orders_valid.csv --contract examples/orders.contract.json
PASS: examples/orders_valid.csv against contract 'orders'
5 rows checked, 0 skipped, 0 errors, 0 warnings
$ echo $?
0
```

## Setup

Requires Python 3.11 or newer. CI tests Python 3.11–3.14 on Linux and 3.13 on macOS.
There are no runtime dependencies; pytest is only needed to run the tests.

```bash
git clone https://github.com/SohamMessi10/data-contract-inspector.git
cd data-contract-inspector
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m pytest
```

## Usage

```bash
contract-inspector check DATA.csv --contract CONTRACT.json [--report OUT.json] [--json] [--max-findings N]
```

| Option | Effect |
|---|---|
| `--contract`, `-c` | The contract file (required). |
| `--report`, `-r` | Also save the full JSON report. Written atomically; refuses to overwrite an input file. |
| `--json` | Print the JSON report instead of the text summary, for piping into other tools. |
| `--max-findings` | How many findings the text summary shows (default 20). The JSON report always has all of them. |

`python -m contract_inspector ...` works the same way.

### Exit codes

Scripts and CI can act on the result without parsing any text:

| Code | Meaning |
|---|---|
| 0 | The dataset meets the contract. Warnings, such as an extra column, are allowed. |
| 1 | The dataset was read but breaks the contract. |
| 2 | Bad arguments or an invalid contract. Every contract problem is listed at once. |
| 3 | The dataset could not be read: missing, not UTF-8, no header, unclosed quote, and so on. |
| 4 | The checks ran, but the `--report` file could not be written. |

For example, to stop a pipeline before it loads bad data:

```bash
contract-inspector check daily_orders.csv -c orders.contract.json --report reports/orders.json || exit 1
```

### From Python

```python
from contract_inspector import load_contract, inspect

contract = load_contract("examples/orders.contract.json")
for finding in inspect(contract, "examples/orders_invalid.csv").findings:
    print(finding.line, finding.column, finding.rule, finding.message)
```

## What it checks

| Check | Rule id | Notes |
|---|---|---|
| Rows with the wrong number of fields | `field_count` | The row is reported and excluded from value checks. |
| Required column missing | `missing_column` | Exact, case-sensitive match. Hints when only whitespace differs. |
| Column not in the contract | `unexpected_column` | A warning, not an error. |
| Wrong type | `type` | `integer`, `number`, or `string`. No coercion: `1.0` is not an integer, and `1e3` is not a number. |
| Out of range | `min`, `max` | Inclusive bounds, compared as exact decimals. |
| Blank where none allowed | `null` | Reported on every offending line. |
| Too many blanks | `null_fraction` | One finding per column when the share of blanks exceeds the limit. |
| Duplicate primary key | `duplicate_key` | Points back to the first occurrence. `1003` and `01003` are the same integer key. |

The full rules, including exactly which text counts as an integer or a number, are in
[`docs/contract-spec.md`](docs/contract-spec.md).

## How it works

```
contract.json --> contract.py  validate the contract itself (unknown keys, NaN bounds, ...)
                      |
data.csv -------> dataset.py   read the CSV: line numbers, header checks, field counts
                      |
                  rules.py     check types, ranges, blanks, and primary keys
                      |
                  report.py    build the JSON report and the text summary
                      |
                  cli.py       arguments, output, and exit codes
```

Each stage is a plain function with no global state, so each one is tested on its own.

## Design decisions

- **Report, never repair.** The tool doesn't fix data, because a fix needs a person who knows
  what the value should be. Values stay raw text until a rule explicitly decides what it accepts.
- **Strict about the contract too.** A typo such as `"mxa": 10` would otherwise disable a check
  without anyone noticing, so unknown keys, duplicate JSON keys, `NaN` bounds, and `true` used as
  a number are all rejected. Every contract problem is reported at once.
- **"Unreadable" is not "invalid."** A file that can't be read (exit 3) is a different problem
  from a file that breaks the rules (exit 1), and a pipeline may handle them differently.
- **Deterministic output.** The report has no timestamps or absolute paths, so the same input
  gives a byte-identical report that can be diffed or stored as a test fixture.
- **Exact numbers.** Bounds are compared as `Decimal`, so a value sitting exactly on a limit is
  never misjudged because of floating-point rounding.
- **Standard library only.** The checks need only `csv`, `json`, `re`, and `decimal`, so there is
  nothing to install and no dependency to keep up to date.

## Testing

- **138 tests** (pytest) cover the contract loader, CSV reading, every rule, the report format,
  and the command, including one test that runs the installed command as a subprocess.
- **Acceptance and golden-file tests:** the broken example must produce exactly the five
  documented findings, and its JSON report must match the committed file byte for byte.
- **Mutation checks:** during development, each important rule was broken on purpose to confirm
  that at least one test failed. These checks were done by hand and are not part of CI. They
  found one weak test, now fixed. See [`PROGRESS.md`](PROGRESS.md).
- **Continuous integration:** GitHub Actions runs the tests on Python 3.11–3.14 on Linux and
  3.13 on macOS. It also runs the installed command and asserts exit codes 0 to 3.

Bugs found while building it, and how they were handled:

- With default settings, Python's `csv` module doesn't treat an **unclosed quote** as an error.
  It folds every following line into one field, so those rows disappear without a warning. The
  reader now uses `strict=True`, and a regression test covers it.
- A commit was once pushed without a module it imported, which broke `main`. It was fixed in
  a follow-up commit, and the CI added afterwards catches this kind of mistake automatically.

## Limitations

- **The whole file is read into memory.** It has not been benchmarked on large files, and
  streaming large inputs is future work.
- **UTF-8 only.** Other encodings are rejected rather than guessed. An Excel byte-order mark is
  handled.
- **Comma-separated only.** Tabs, semicolons, and other delimiters are not configurable yet.
- **Simple types.** `string`, `integer`, and `number` only. Dates, booleans, allowed-value
  lists, and patterns are not supported yet.
- **Number format.** Plain decimals such as `-2.00`. Thousands separators, currency symbols,
  and scientific notation are reported as invalid by design.
- **One primary-key column.** Composite keys are not supported.
- **Blank lines in a one-column file.** An empty value is indistinguishable from a blank line,
  which is skipped, so empty values must be written as `""`. Files with two or more columns are
  unaffected.
- **Fields over 128 KiB** make the file unreadable, which is Python's `csv` module default limit.

## Possible next steps

Schema drift (comparing two versions of a dataset), more column types, configurable delimiters,
chunked reading for large files after measuring memory use, and a GitHub Action wrapper.

## License

[MIT](LICENSE)

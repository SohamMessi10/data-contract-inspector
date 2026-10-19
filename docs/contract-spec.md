# Data contract specification (v1)

A **data contract** is a JSON file that states what a CSV must look like before anyone
analyzes it. The inspector reports every way a dataset breaks its contract instead of
silently fixing values.

## Contract format

```json
{
  "contract_version": 1,
  "name": "orders",
  "primary_key": "order_id",
  "columns": [
    {"name": "order_id", "type": "integer"},
    {"name": "quantity", "type": "integer", "min": 1, "max": 1000},
    {"name": "coupon_code", "type": "string", "required": false, "max_null_fraction": 1.0}
  ]
}
```

### Top-level keys

| Key | Required | Meaning |
|---|---|---|
| `contract_version` | yes | Must be `1`. Lets the format change later without misreading old contracts. |
| `name` | yes | Non-empty label used in reports. |
| `columns` | yes | Non-empty list of column rules, in the order you want them reported. |
| `primary_key` | no | Name of a declared column whose values must be unique and never null. |

### Column keys

| Key | Default | Meaning |
|---|---|---|
| `name` | — | Exact CSV header text. No leading/trailing whitespace. Unique within the contract. |
| `type` | — | `string`, `integer`, or `number`. |
| `required` | `true` | The column header must be present in the CSV. |
| `max_null_fraction` | `0.0` | Largest allowed share of null cells, from `0` (none) to `1` (all). |
| `min`, `max` | none | Inclusive bounds. Only for `integer`/`number`; must be whole numbers for `integer`. |

### Strictness rules (contract file)

The contract is a configuration file, so mistakes in it are reported rather than ignored:

- Unknown keys are errors. A typo such as `"mxa": 10` would otherwise silently disable a check.
- Duplicate JSON keys are errors. Python's `json` module would otherwise keep only the last one.
- `NaN` and `Infinity` are rejected. A `NaN` bound makes every comparison false, so the check would never fire.
- `true`/`false` are not accepted as numbers, even though Python treats `True == 1`.
- A primary-key column must be `required` with `max_null_fraction` 0.
- All problems in a contract are reported together, not one per run.

## How a CSV file is read (implemented)

- The file must be UTF-8. An Excel byte-order mark is removed; other encodings are rejected, not guessed.
- The first line is the header. Header names must be non-empty and unique, and they are matched
  to the contract exactly: case-sensitive, with no whitespace trimming. A name that matches only
  after trimming is reported with a hint instead of being silently fixed.
- Quoting follows standard CSV rules, so `"a, b"` is one field and a quoted field may span lines.
  An unclosed quote is an error. Python's default lenient mode would otherwise fold every
  following line into one field, and those rows would silently disappear.
- Blank lines are skipped. Line numbers always refer to the physical line in the file where a
  record starts.
- A row whose field count differs from the header is reported (`field_count`) and excluded from
  value checks, because its values cannot be matched to columns reliably.
- A missing required column is an error (`missing_column`). An extra column not in the contract
  is a warning (`unexpected_column`).
- Values are kept as raw text. Type conversion is a separate, explicit step.
- The whole file is read into memory. Large-file streaming is a stretch goal.

**Unreadable file (exit code 3):** missing, a directory, not UTF-8, empty, blank first line, an
unnamed or duplicate header, an unclosed quote, or a single field over 128 KiB.

## How CSV values are checked (implemented)

- A cell is **null** if it is empty or contains only whitespace. In a one-column file an empty
  line is skipped as blank, so an empty value must be written as `""`.
- `integer`: optional `-` followed by ASCII digits 0-9. Leading zeros are allowed (`007` is 7).
  `1.0`, `1e3`, `+5`, `1,000`, and `" 5"` are invalid, not coerced.
- `number`: optional `-`, digits, and an optional decimal part (`19.99`, `-2.00`, `5`).
  `NaN`, `inf`, `1e3`, `.5`, `5.`, `1_000`, and surrounding whitespace are invalid, even though
  Python's `float()` accepts most of them. Values are compared as `Decimal`, so bounds are exact.
- `string`: any non-null text.
- Bounds are inclusive. Null cells skip type and range checks, and a value with the wrong type is
  not range-checked.
- Nulls:
  - `max_null_fraction` 0: every null cell is reported on its own line (`null`).
  - Otherwise, if the share of null rows is above the limit, one column-level finding
    (`null_fraction`) lists the count and the first five lines. Exactly at the limit passes.
- Primary key: each repeat of an earlier value is reported (`duplicate_key`) and points at the
  first occurrence. Integer keys compare by value, so `1003` and `01003` are duplicates. String
  keys are compared exactly, including case.
- Rows excluded for a wrong field count are not value-checked or counted.
- Findings are sorted by line, then by contract column order. File-wide findings (no line)
  come last. The same input always gives the same findings in the same order.
- Findings refer to **file line numbers** (the header is line 1).

## JSON report (implemented)

Example: [`examples/orders_invalid.report.json`](../examples/orders_invalid.report.json).

| Key | Meaning |
|---|---|
| `report_version` | `1`. Bumped if the report format changes incompatibly. |
| `contract` | The contract's `name`. |
| `dataset` | The dataset path as the user gave it. Absolute paths are not added. |
| `status` | `fail` if there is at least one error, otherwise `pass`. Warnings alone pass. |
| `summary.rows_checked` | Data rows whose values were checked. |
| `summary.rows_skipped` | Rows excluded for a wrong field count. |
| `summary.errors`, `summary.warnings` | Finding counts by severity. |
| `summary.by_rule` | Finding counts by rule id, sorted by rule id. |
| `findings[]` | `severity`, `rule`, `line` (`null` for file-wide findings), `column` (`null` if none), `message`. Same order as above. |

The report has no timestamp or machine-specific data, so the same input gives a byte-identical
file. It is UTF-8 JSON with 2-space indentation and a trailing newline. It is written atomically
(temporary file in the same directory, then rename), so a crash never leaves a partial report.

## Command line and exit codes (implemented)

```bash
contract-inspector check DATA.csv --contract CONTRACT.json [--report OUT.json] [--json] [--max-findings N]
```

`python -m contract_inspector ...` works the same way. The text summary (or, with `--json`, the
JSON report) goes to stdout. Errors running the tool go to stderr, so stdout stays safe to pipe.

| Code | Meaning |
|---|---|
| 0 | Dataset satisfies the contract. Warnings are allowed. |
| 1 | Dataset was read successfully but violates the contract. |
| 2 | Usage or contract error: bad arguments, invalid or missing contract, or `--report` pointing at an input file. |
| 3 | Dataset could not be read (see "Unreadable file" above). Nothing was checked and no report is written. |
| 4 | Checks ran and the result was printed, but the `--report` file could not be written. |

The contract is loaded before the dataset, so when both are broken the exit code is 2.
`--report` refuses to overwrite the dataset or contract, including through `./` or symlinks.

## Acceptance fixture

`examples/` contains **synthetic demo data** (fictional orders, `example.com` addresses).

`examples/orders_valid.csv` must produce **no findings**.

`examples/orders_invalid.csv` must produce **exactly** these five findings:

| Line | Column | Rule | Message |
|---|---|---|---|
| 3 | `quantity` | `min` | `'0' is below the minimum of 1` |
| 4 | `customer_email` | `null` | `value is null; column allows no nulls (1 of 6 rows null)` |
| 5 | `order_id` | `duplicate_key` | `'1003' duplicates the primary key on line 4` |
| 6 | `quantity` | `type` | `'three' is not an integer` |
| 7 | `unit_price` | `min` | `'-2.00' is below the minimum of 0` |

This is enforced by `test_invalid_fixture_produces_exactly_the_documented_findings`.

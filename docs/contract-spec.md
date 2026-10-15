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

## How CSV values will be interpreted (implemented in later milestones)

- The first row is the header. Extra columns not in the contract are reported as a warning, not an error.
- A cell is **null** if it is empty or contains only whitespace.
- `integer`: optional `-` sign followed by digits only. `1.0`, `1e3`, `" 5"` are invalid, not coerced.
- `number`: a decimal such as `-2.00` or `19.99`. `NaN`, `inf`, and surrounding whitespace are invalid.
- `string`: any non-null text.
- Range and type checks skip null cells; nulls are governed only by `max_null_fraction`.
- Findings refer to **file line numbers** (the header is line 1).

## Exit codes (implemented in the CLI milestone)

| Code | Meaning |
|---|---|
| 0 | Dataset satisfies the contract. |
| 1 | Dataset was read successfully but violates the contract. |
| 2 | Usage or contract error (bad arguments, invalid contract). |
| 3 | Dataset could not be read (missing, unreadable, not decodable, no header). |

## Acceptance fixture

`examples/` contains **synthetic demo data** (fictional orders, `example.com` addresses).

`examples/orders_valid.csv` must produce **no findings**.

`examples/orders_invalid.csv` must produce **exactly** these five findings:

| Line | Column | Problem |
|---|---|---|
| 3 | `quantity` | `0` is below the minimum of 1 |
| 4 | `customer_email` | null; column allows 0% nulls (1 of 6 rows null) |
| 5 | `order_id` | `1003` duplicates the primary key on line 4 |
| 6 | `quantity` | `three` is not an integer |
| 7 | `unit_price` | `-2.00` is below the minimum of 0 |

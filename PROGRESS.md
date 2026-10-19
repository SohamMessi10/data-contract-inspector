# Progress

## Completed

### Milestone 1: Contract specification and loader
- Repository layout (`src/` package, `tests/`, `examples/`, `docs/`), `pyproject.toml`, `.gitignore`.
- Contract format v1 documented in `docs/contract-spec.md`, including CSV value rules,
  exit codes, and the acceptance fixture with its 5 expected findings.
- `load_contract` / `parse_contract` validate the contract file and report every problem at once.
- Synthetic fixtures: `examples/orders_valid.csv`, `examples/orders_invalid.csv`.

### Milestone 2: CSV loader and column checks
- `load_dataset` reads a UTF-8 CSV with true file line numbers and keeps values as raw text.
- Unreadable files raise `DatasetError`: missing, directory, non-UTF-8, empty, bad or duplicate
  header, unclosed quote, oversized field.
- Rows with the wrong field count become `field_count` findings and are excluded.
- `check_columns` reports missing required columns (error) and unexpected columns (warning),
  with a hint when the only difference is whitespace.
- Bug found while testing: Python's csv module silently swallows the rest of the file after an
  unclosed quote. Fixed with `strict=True`, plus a regression test.

### Milestone 3: Value rules
- `check_values` checks types (no silent coercion), inclusive min/max with exact `Decimal`
  comparison, nulls (per line when none are allowed, one column finding when over a fraction),
  and primary-key duplicates (integer keys compare by value).
- `inspect_dataset` runs every check and returns findings in a stable order.
- The acceptance fixture produces exactly the 5 documented findings; the valid fixture produces none.
- Mutation testing (breaking each rule on purpose) exposed a weak test: in a one-column CSV an
  empty line is skipped as blank, so the "exactly at the null limit" test was really testing
  0% nulls. Fixed by writing empty values as `""`; the quirk is documented in the spec.

## Commands verified

| Where | Python | Command | Result |
|---|---|---|---|
| Soham's Mac (conda env `dci`) | 3.13.5 | `python -m pytest` | 30 passed (milestone 1) |
| Soham's Mac (conda env `dci`) | 3.13.5 | `python -m pytest` | 53 passed (milestone 2) |
| Claude's Linux workspace | 3.13 | `python -m pytest` | 100 passed (milestone 3) |

## Next

- Milestone 4: machine-readable JSON report of the findings.
- Then: CLI with exit codes, CI, demo README.

## Concepts to review
- Why strict config parsing (rejecting unknown keys) catches typos that would silently disable checks.
- `json` quirks: duplicate keys keep the last value; `NaN`/`Infinity` are accepted by default.
- `bool` is a subclass of `int` in Python (`True == 1`).
- Frozen dataclasses as immutable value objects.
- `src/` layout and editable installs (`pip install -e`).
- "Can't read the file" (DatasetError) vs "file breaks the contract" (Finding).
- `newline=""`, `utf-8-sig`, and `strict=True` when reading CSVs with the csv module.
- Record line number vs physical line number when a quoted field spans lines.
- Why `Decimal(str(0.1))` is exact but `float` and `Decimal(0.1)` are not.
- Regex `[0-9]` vs `\d` (Unicode digits).
- Mutation testing: a test only proves something if breaking the code makes it fail.

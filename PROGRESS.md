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

## Commands verified

| Where | Python | Command | Result |
|---|---|---|---|
| Soham's Mac (conda env `dci`) | 3.13.5 | `python -m pytest` | 30 passed (milestone 1) |
| Claude's Linux workspace | 3.13 | `python -m pytest` | 53 passed (milestone 2) |

## Next

- Milestone 3: value rules (type, range, null fraction, primary-key uniqueness). The acceptance
  fixture must produce exactly the 5 findings in the spec.
- Then: JSON report, CLI with exit codes, edge-case tests, CI, demo README.

## Concepts to review
- Why strict config parsing (rejecting unknown keys) catches typos that would silently disable checks.
- `json` quirks: duplicate keys keep the last value; `NaN`/`Infinity` are accepted by default.
- `bool` is a subclass of `int` in Python (`True == 1`).
- Frozen dataclasses as immutable value objects.
- `src/` layout and editable installs (`pip install -e`).
- "Can't read the file" (DatasetError) vs "file breaks the contract" (Finding).
- `newline=""`, `utf-8-sig`, and `strict=True` when reading CSVs with the csv module.
- Record line number vs physical line number when a quoted field spans lines.

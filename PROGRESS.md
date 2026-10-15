# Progress

## Completed

### Milestone 1 — Contract specification and loader
- Repository layout (`src/` package, `tests/`, `examples/`, `docs/`), `pyproject.toml`, `.gitignore`.
- Contract format v1 documented in `docs/contract-spec.md`, including CSV value rules,
  exit codes, and the acceptance fixture with its 5 expected findings.
- `load_contract` / `parse_contract` validate the contract file and report every problem at once.
- Synthetic fixtures: `examples/orders_valid.csv`, `examples/orders_invalid.csv`.

## Commands verified

Verified in Claude's Linux workspace (Python 3.13.16, pytest 9.1.1) on 2026-10-15:

```bash
python3 -m venv .venv && source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m pytest          # 30 passed
```

Not yet verified on Soham's Mac.

## Next

- Milestone 2 — CSV loader: read header + rows with line numbers; report missing required
  columns; distinguish unreadable files (exit code 3 later) from invalid data.
- Milestone 3 — Value rules: type, range, null fraction, primary-key uniqueness. The
  acceptance fixture must produce exactly the 5 findings in the spec.
- Then: JSON report, CLI with exit codes, edge-case tests, CI, demo README.

## Concepts to review
- Why strict config parsing (rejecting unknown keys) catches typos that would silently disable checks.
- `json` quirks: duplicate keys keep the last value; `NaN`/`Infinity` are accepted by default.
- `bool` is a subclass of `int` in Python (`True == 1`).
- Frozen dataclasses as immutable value objects.
- `src/` layout and editable installs (`pip install -e`).

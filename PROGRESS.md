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

### Milestone 4: JSON report and terminal summary
- `inspect()` returns the dataset and sorted findings; `build_report` turns them into a
  versioned, deterministic JSON report (status, summary counts, findings).
- `write_report` writes atomically (temporary file + `os.replace`), so a crash keeps the old file.
- `format_summary` prints a short human-readable summary, truncated after 20 findings.
- Golden file `examples/orders_invalid.report.json` is compared byte-for-byte in a test.
- Mutation-checked: non-atomic write, status logic, rule ordering, and non-ASCII output each
  break a test.

### Milestone 5: Command-line tool
- `contract-inspector check DATA --contract C [--report OUT] [--json] [--max-findings N]`,
  also runnable as `python -m contract_inspector`.
- Exit codes 0 pass, 1 violations, 2 usage/contract, 3 unreadable dataset, 4 report not written.
- Results on stdout, errors on stderr; `--json` makes stdout pure JSON.
- Refuses `--report` paths that resolve to an input file, so a typo can't overwrite the data.
- Tests call `main()` directly, plus one subprocess test that runs the real command.

### Fix: missing report module (`f4e5e72`)
- The milestone 5 commit was pushed without milestone 4's files, so `main` failed to import
  `contract_inspector.report`. Fixed with a separate commit adding the 5 missing files.
- Lesson: run the tests before every commit and stop if they fail. CI now enforces this.

### Milestone 6: Continuous integration
- `.github/workflows/tests.yml` runs on pushes to `main`, pull requests, and manual dispatch.
- Matrix: Python 3.11, 3.12, 3.13, 3.14 on Ubuntu, plus 3.13 on macOS.
- Besides pytest, it runs the installed command and asserts exit codes 0/1/2/3, and diffs a
  generated report against the golden file.
- Read-only token permissions, no persisted checkout credentials, cancels outdated runs.
- Pinned `actions/checkout@v7` and `actions/setup-python@v7` (released July 2026, node24).

### Milestone 7: README, demo, and license
- README rewritten for a first-time reader: the problem (silent coercion, with real Python
  examples), a broken-to-passing demo, usage, exit codes, checks, architecture, design decisions,
  testing, bugs found, limitations, and next steps.
- Every console block, the demo CSV, and the contract in the README were checked against real
  output and files; every relative link resolves.
- MIT license added (`LICENSE`, plus `license` in `pyproject.toml`).

**Project status: MVP complete.** All acceptance criteria from the brief are met: the fixture
produces exactly the known findings, edge cases are handled with clear errors, output is
deterministic, and there are documented exit codes, CI, a demo, and limitations.

## Commands verified

| Where | Python | Command | Result |
|---|---|---|---|
| Soham's Mac (conda env `dci`) | 3.13.5 | `python -m pytest` | 30 passed (milestone 1) |
| Soham's Mac (conda env `dci`) | 3.13.5 | `python -m pytest` | 53 passed (milestone 2) |
| Soham's Mac (conda env `dci`) | 3.13.5 | `python -m pytest` | 100 passed (milestone 3, pushed `db81338`) |
| Claude's Linux workspace | 3.13 | `python -m pytest` | 114 passed (milestone 4) |
| Claude's Linux workspace | 3.13 | `python -m pytest`; each exit path run by hand | 138 passed (milestone 5) |
| Claude's Linux workspace | 3.11, 3.12, 3.14 | `python -m pytest` | 138 passed on each |
| Claude's Linux workspace | 3.13 | workflow's end-to-end step run locally | passes; fails when exit code 3 is broken |
| GitHub Actions | 3.11–3.14 (Linux), 3.13 (macOS) | `tests` workflow on `20b220e` | passed (21 s) |

## Next

- Optional stretch work, only if useful: schema-drift comparison, more column types, configurable
  delimiter, memory benchmark before any streaming work.
- Next project in the brief: SplitLedger.

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
- Deterministic output and golden-file tests.
- Atomic writes: why write-then-rename is safe and writing in place is not.
- Exit codes and stdout vs stderr as a program's interface to scripts.
- `[project.scripts]` entry points and `python -m package` (`__main__.py`).
- CI: workflows, triggers, matrix builds, least-privilege permissions.

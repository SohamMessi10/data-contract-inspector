"""Read a CSV file and check its header against a contract.

Two kinds of failure are kept separate on purpose:

- DatasetError: the file cannot be read as a CSV at all (missing, not UTF-8,
  no header, ambiguous header). Nothing can be checked. The CLI will map this
  to exit code 3.
- Finding: the file was read, but something in it breaks the contract (a
  missing column, a row with the wrong number of fields). These are collected
  and reported together. The CLI will map these to exit code 1.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from contract_inspector.contract import Contract


class DatasetError(Exception):
    """The dataset file could not be read, so no checks were run."""


@dataclass(frozen=True)
class Row:
    line: int  # file line where this record starts (the header is line 1)
    values: tuple[str, ...]


@dataclass(frozen=True)
class Dataset:
    path: Path
    header: tuple[str, ...]
    rows: tuple[Row, ...]


@dataclass(frozen=True)
class Finding:
    severity: str  # "error" breaks the contract; "warning" is worth a look
    rule: str  # short machine-readable id, e.g. "missing_column"
    message: str
    line: int | None = None
    column: str | None = None


def load_dataset(path: str | Path) -> tuple[Dataset, list[Finding]]:
    """Read a CSV into memory.

    Returns the dataset plus structural findings (rows with the wrong number of
    fields). Raises DatasetError if the file cannot be read as a CSV.
    """
    path = Path(path)
    try:
        # newline="" is required by the csv module so quoted fields containing
        # line breaks are read correctly. utf-8-sig strips the invisible byte-order
        # mark that Excel adds, which would otherwise end up in the first header name.
        with path.open(encoding="utf-8-sig", newline="") as handle:
            return _read(path, handle)
    except FileNotFoundError:
        raise DatasetError(f"dataset file not found: {path}") from None
    except IsADirectoryError:
        raise DatasetError(f"dataset path is a directory, not a file: {path}") from None
    except UnicodeDecodeError as exc:
        raise DatasetError(
            f"{path} is not valid UTF-8 text (byte offset {exc.start}); "
            "re-save it as UTF-8 CSV"
        ) from None
    except OSError as exc:
        raise DatasetError(f"cannot read dataset file {path}: {exc}") from None


def _read(path: Path, handle) -> tuple[Dataset, list[Finding]]:
    # strict=True makes an unclosed quote an error. Without it, the csv module
    # silently folds every following line into one field and those rows vanish.
    reader = csv.reader(handle, strict=True)
    try:
        header = next(reader, None)
        if header is None or header == []:
            raise DatasetError(f"{path} is empty or its first line is blank; expected a header row")
        _check_header(path, header)

        rows: list[Row] = []
        findings: list[Finding] = []
        record_start = reader.line_num + 1
        for values in reader:
            line = record_start
            record_start = reader.line_num + 1  # next record starts after this one ends
            if not values:
                continue  # blank line, e.g. a trailing newline at the end of the file
            if len(values) != len(header):
                findings.append(
                    Finding(
                        severity="error",
                        rule="field_count",
                        line=line,
                        message=(
                            f"row has {len(values)} fields but the header has "
                            f"{len(header)}; row was not checked further"
                        ),
                    )
                )
                continue
            rows.append(Row(line=line, values=tuple(values)))
    except csv.Error as exc:
        raise DatasetError(f"{path} is not a readable CSV (line {reader.line_num}): {exc}") from None

    return Dataset(path=path, header=tuple(header), rows=tuple(rows)), findings


def _check_header(path: Path, header: list[str]) -> None:
    for position, name in enumerate(header, start=1):
        if name == "":
            raise DatasetError(f"{path}: header column {position} has no name")
    seen: set[str] = set()
    for name in header:
        if name in seen:
            raise DatasetError(
                f"{path}: header names column {name!r} more than once, "
                "so its values are ambiguous"
            )
        seen.add(name)


def check_columns(contract: Contract, dataset: Dataset) -> list[Finding]:
    """Compare the CSV header with the columns the contract declares."""
    findings: list[Finding] = []
    present = set(dataset.header)
    declared = {rule.name for rule in contract.columns}
    stripped = {name.strip(): name for name in dataset.header}

    for rule in contract.columns:
        if rule.name in present or not rule.required:
            continue
        message = f"required column {rule.name!r} is missing"
        near_miss = stripped.get(rule.name)
        if near_miss is not None:
            # Don't silently strip: tell the user exactly what is in the file.
            message += f" (the header has {near_miss!r}, which includes extra whitespace)"
        findings.append(
            Finding(severity="error", rule="missing_column", column=rule.name, message=message)
        )

    for name in dataset.header:
        if name not in declared:
            findings.append(
                Finding(
                    severity="warning",
                    rule="unexpected_column",
                    column=name,
                    message=f"column {name!r} is not in the contract and was not checked",
                )
            )
    return findings

"""Check the values in a dataset against the contract's column rules.

Values arrive as raw text from the loader. Each rule decides explicitly what
text it accepts, so nothing is silently coerced: "1.0" is not an integer, and
"1e3" is not a number, even though Python would happily convert both.
"""

from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path

from contract_inspector.contract import ColumnRule, Contract
from contract_inspector.dataset import Dataset, Finding, check_columns, load_dataset

# [0-9] rather than \d: in Python, \d also matches non-ASCII digits such as "٣".
_INTEGER = re.compile(r"-?[0-9]+")
_NUMBER = re.compile(r"-?[0-9]+(\.[0-9]+)?")


def is_null(raw: str) -> bool:
    return raw.strip() == ""


def parse_value(rule: ColumnRule, raw: str) -> int | Decimal | str | None:
    """Return the typed value, or None if `raw` is not valid for the column type."""
    if rule.type == "integer":
        return int(raw) if _INTEGER.fullmatch(raw) else None
    if rule.type == "number":
        # Decimal, not float: "0.1" stays exactly 0.1, so bound checks are exact.
        return Decimal(raw) if _NUMBER.fullmatch(raw) else None
    return raw


def check_values(contract: Contract, dataset: Dataset) -> list[Finding]:
    """Type, range, null, and primary-key checks for every column in the header."""
    findings: list[Finding] = []
    position = {name: index for index, name in enumerate(dataset.header)}
    total_rows = len(dataset.rows)

    for rule in contract.columns:
        index = position.get(rule.name)
        if index is None:
            continue  # a missing column is reported by check_columns
        null_lines: list[int] = []
        first_seen: dict[object, int] = {}  # primary-key value -> line it first appeared

        for row in dataset.rows:
            raw = row.values[index]
            if is_null(raw):
                null_lines.append(row.line)
                continue

            value = parse_value(rule, raw)
            if value is None:
                findings.append(_row_finding("type", row.line, rule, f"{raw!r} is not {_article(rule.type)}"))
                continue

            if rule.min is not None and value < _exact(rule.min):
                findings.append(_row_finding("min", row.line, rule, f"{raw!r} is below the minimum of {rule.min}"))
            if rule.max is not None and value > _exact(rule.max):
                findings.append(_row_finding("max", row.line, rule, f"{raw!r} is above the maximum of {rule.max}"))

            if rule.name == contract.primary_key:
                # Compare typed values, so "1003" and "01003" count as the same integer key.
                if value in first_seen:
                    findings.append(
                        _row_finding(
                            "duplicate_key",
                            row.line,
                            rule,
                            f"{raw!r} duplicates the primary key on line {first_seen[value]}",
                        )
                    )
                else:
                    first_seen[value] = row.line

        findings.extend(_null_findings(rule, null_lines, total_rows))
    return findings


def _null_findings(rule: ColumnRule, null_lines: list[int], total_rows: int) -> list[Finding]:
    if not null_lines:
        return []
    summary = f"{len(null_lines)} of {total_rows} rows null"
    if rule.max_null_fraction == 0:
        # No nulls allowed: point at every offending line, since each one is fixable.
        return [
            _row_finding("null", line, rule, f"value is null; column allows no nulls ({summary})")
            for line in null_lines
        ]
    if len(null_lines) / total_rows <= rule.max_null_fraction:
        return []
    shown = ", ".join(str(line) for line in null_lines[:5])
    more = ", ..." if len(null_lines) > 5 else ""
    return [
        Finding(
            severity="error",
            rule="null_fraction",
            column=rule.name,
            message=(
                f"{summary} ({len(null_lines) / total_rows:.0%}), above the limit of "
                f"{rule.max_null_fraction:.0%}; null on lines {shown}{more}"
            ),
        )
    ]


def inspect_dataset(contract: Contract, path: str | Path) -> list[Finding]:
    """Run every check on a CSV file and return findings in a stable order.

    Raises DatasetError if the file cannot be read.
    """
    dataset, structural = load_dataset(path)
    findings = structural + check_columns(contract, dataset) + check_values(contract, dataset)
    column_order = {rule.name: i for i, rule in enumerate(contract.columns)}

    def sort_key(finding: Finding):
        # Row findings in file order first, then file-wide findings (line None).
        return (
            finding.line is None,
            finding.line or 0,
            column_order.get(finding.column, len(column_order)),
            finding.rule,
        )

    return sorted(findings, key=sort_key)


def _row_finding(rule_id: str, line: int, rule: ColumnRule, message: str) -> Finding:
    return Finding(severity="error", rule=rule_id, line=line, column=rule.name, message=message)


def _exact(bound: int | float) -> int | Decimal:
    # Decimal(str(0.1)) is exactly 0.1; Decimal(0.1) would be 0.1000000000000000055...
    return bound if isinstance(bound, int) else Decimal(str(bound))


def _article(type_name: str) -> str:
    return "an integer" if type_name == "integer" else "a number"

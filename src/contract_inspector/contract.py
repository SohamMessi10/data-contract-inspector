"""Load and check a data contract: the JSON file describing what a CSV must look like.

This module only validates the *contract itself*. Checking a CSV against a
contract comes in a later milestone. Every problem found in the contract is
collected and reported together, so a user can fix them all in one pass.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SUPPORTED_CONTRACT_VERSION = 1
COLUMN_TYPES = ("string", "integer", "number")
NUMERIC_TYPES = ("integer", "number")

_CONTRACT_KEYS = {"contract_version", "name", "primary_key", "columns"}
_COLUMN_KEYS = {"name", "type", "required", "max_null_fraction", "min", "max"}


class ContractError(Exception):
    """The contract file is unreadable or does not follow the contract format."""

    def __init__(self, problems: list[str]) -> None:
        self.problems = list(problems)
        lines = "\n".join(f"  - {problem}" for problem in self.problems)
        super().__init__(f"invalid contract:\n{lines}")


@dataclass(frozen=True)
class ColumnRule:
    name: str
    type: str
    required: bool = True
    max_null_fraction: float = 0.0
    min: int | float | None = None
    max: int | float | None = None


@dataclass(frozen=True)
class Contract:
    name: str
    columns: tuple[ColumnRule, ...]
    primary_key: str | None = None


def load_contract(path: str | Path) -> Contract:
    """Read a contract JSON file and return a validated Contract."""
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise ContractError([f"contract file not found: {path}"]) from None
    except (OSError, UnicodeDecodeError) as exc:
        raise ContractError([f"cannot read contract file {path}: {exc}"]) from None

    try:
        data = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_non_finite,
        )
    except json.JSONDecodeError as exc:
        raise ContractError(
            [f"{path} is not valid JSON (line {exc.lineno}, column {exc.colno}): {exc.msg}"]
        ) from None
    return parse_contract(data)


def parse_contract(data: Any) -> Contract:
    """Validate already-decoded JSON data and build a Contract."""
    if not isinstance(data, dict):
        raise ContractError([f"top level must be a JSON object, got {_json_type(data)}"])

    problems: list[str] = []
    for key in sorted(data.keys() - _CONTRACT_KEYS):
        problems.append(f"unknown top-level key {key!r}")

    version = data.get("contract_version")
    if version is None:
        problems.append("missing 'contract_version'")
    elif type(version) is not int or version != SUPPORTED_CONTRACT_VERSION:
        # `type(...) is int` rejects True, which Python otherwise treats as equal to 1.
        problems.append(
            f"unsupported contract_version {version!r} "
            f"(supported: {SUPPORTED_CONTRACT_VERSION})"
        )

    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        problems.append("'name' must be a non-empty string")

    raw_columns = data.get("columns")
    columns: list[ColumnRule] = []
    if not isinstance(raw_columns, list) or not raw_columns:
        problems.append("'columns' must be a non-empty list")
    else:
        seen: set[str] = set()
        for index, raw in enumerate(raw_columns):
            rule = _parse_column(raw, index, problems)
            if rule is None:
                continue
            if rule.name in seen:
                problems.append(f"column {rule.name!r} is declared more than once")
            seen.add(rule.name)
            columns.append(rule)

    primary_key = data.get("primary_key")
    if primary_key is not None:
        if not isinstance(primary_key, str):
            problems.append("'primary_key' must be a column name (string)")
        else:
            pk_rule = next((c for c in columns if c.name == primary_key), None)
            if pk_rule is None:
                problems.append(f"primary_key {primary_key!r} is not a declared column")
            elif not pk_rule.required or pk_rule.max_null_fraction != 0:
                problems.append(
                    f"primary_key column {primary_key!r} must be required "
                    "and have max_null_fraction 0"
                )

    if problems:
        raise ContractError(problems)
    return Contract(name=name, columns=tuple(columns), primary_key=primary_key)


def _parse_column(raw: Any, index: int, problems: list[str]) -> ColumnRule | None:
    """Validate one column entry. Appends to `problems`; returns None if invalid."""
    where = f"columns[{index}]"
    if not isinstance(raw, dict):
        problems.append(f"{where} must be an object, got {_json_type(raw)}")
        return None

    problems_before = len(problems)

    name = raw.get("name")
    if not isinstance(name, str) or not name.strip():
        problems.append(f"{where}: 'name' must be a non-empty string")
    elif name != name.strip():
        problems.append(f"{where}: name {name!r} has leading or trailing whitespace")
    else:
        where = f"column {name!r}"

    for key in sorted(raw.keys() - _COLUMN_KEYS):
        problems.append(f"{where}: unknown key {key!r}")

    col_type = raw.get("type")
    if col_type not in COLUMN_TYPES:
        problems.append(f"{where}: 'type' must be one of {', '.join(COLUMN_TYPES)}")

    required = raw.get("required", True)
    if not isinstance(required, bool):
        problems.append(f"{where}: 'required' must be true or false")

    max_null_fraction = raw.get("max_null_fraction", 0.0)
    if not _is_number(max_null_fraction) or not 0 <= max_null_fraction <= 1:
        problems.append(f"{where}: 'max_null_fraction' must be a number from 0 to 1")

    bounds: dict[str, int | float | None] = {}
    for bound in ("min", "max"):
        value = raw.get(bound)
        bounds[bound] = value
        if value is None:
            continue
        if col_type not in NUMERIC_TYPES:
            problems.append(f"{where}: '{bound}' is only allowed on integer or number columns")
        elif not _is_number(value):
            problems.append(f"{where}: '{bound}' must be a number")
        elif col_type == "integer" and not isinstance(value, int):
            problems.append(f"{where}: '{bound}' must be a whole number for an integer column")

    low, high = bounds["min"], bounds["max"]
    if _is_number(low) and _is_number(high) and low > high:
        problems.append(f"{where}: 'min' ({low}) is greater than 'max' ({high})")

    if len(problems) > problems_before:
        return None
    return ColumnRule(
        name=name,
        type=col_type,
        required=required,
        max_null_fraction=float(max_null_fraction),
        min=low,
        max=high,
    )


def _is_number(value: Any) -> bool:
    # bool is a subclass of int in Python, so exclude it explicitly.
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return math.isfinite(value)


def _json_type(value: Any) -> str:
    if isinstance(value, list):
        return "array"
    if isinstance(value, str):
        return "string"
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    return type(value).__name__


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    # Python's json module silently keeps the LAST duplicate key; we refuse instead.
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ContractError([f"duplicate JSON key {key!r} in the same object"])
        result[key] = value
    return result


def _reject_non_finite(token: str) -> Any:
    # Python's json module accepts NaN/Infinity, which are not valid JSON. A NaN
    # bound would make every comparison false and silently disable a check.
    raise ContractError([f"{token} is not allowed in a contract (not valid JSON)"])

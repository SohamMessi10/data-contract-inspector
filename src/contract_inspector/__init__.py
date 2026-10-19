"""Data Contract Inspector: check a CSV against an agreed schema before it is used."""

from contract_inspector.contract import (
    ColumnRule,
    Contract,
    ContractError,
    load_contract,
    parse_contract,
)
from contract_inspector.dataset import (
    Dataset,
    DatasetError,
    Finding,
    Row,
    check_columns,
    load_dataset,
)
from contract_inspector.report import build_report, format_summary, to_json, write_report
from contract_inspector.rules import (
    Inspection,
    check_values,
    inspect,
    inspect_dataset,
    is_null,
    parse_value,
)

__all__ = [
    "ColumnRule",
    "Contract",
    "ContractError",
    "Dataset",
    "DatasetError",
    "Finding",
    "Inspection",
    "Row",
    "build_report",
    "check_columns",
    "check_values",
    "format_summary",
    "inspect",
    "inspect_dataset",
    "is_null",
    "load_contract",
    "load_dataset",
    "parse_contract",
    "parse_value",
    "to_json",
    "write_report",
]
__version__ = "0.1.0"

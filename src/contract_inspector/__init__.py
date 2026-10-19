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
from contract_inspector.rules import check_values, inspect_dataset, is_null, parse_value

__all__ = [
    "ColumnRule",
    "Contract",
    "ContractError",
    "Dataset",
    "DatasetError",
    "Finding",
    "Row",
    "check_columns",
    "check_values",
    "inspect_dataset",
    "is_null",
    "load_contract",
    "load_dataset",
    "parse_contract",
    "parse_value",
]
__version__ = "0.1.0"

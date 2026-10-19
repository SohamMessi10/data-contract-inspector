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

__all__ = [
    "ColumnRule",
    "Contract",
    "ContractError",
    "Dataset",
    "DatasetError",
    "Finding",
    "Row",
    "check_columns",
    "load_contract",
    "load_dataset",
    "parse_contract",
]
__version__ = "0.1.0"

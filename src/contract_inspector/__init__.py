"""Data Contract Inspector: check a CSV against an agreed schema before it is used."""

from contract_inspector.contract import (
    ColumnRule,
    Contract,
    ContractError,
    load_contract,
    parse_contract,
)

__all__ = ["ColumnRule", "Contract", "ContractError", "load_contract", "parse_contract"]
__version__ = "0.1.0"

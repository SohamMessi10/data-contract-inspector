import json
from pathlib import Path

import pytest

from contract_inspector import ColumnRule, ContractError, load_contract, parse_contract

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def minimal(**overrides):
    """A valid contract dict; tests override one piece at a time."""
    data = {
        "contract_version": 1,
        "name": "orders",
        "columns": [{"name": "order_id", "type": "integer"}],
    }
    data.update(overrides)
    return data


def problems_for(data):
    with pytest.raises(ContractError) as excinfo:
        parse_contract(data)
    return excinfo.value.problems


# --- valid contracts --------------------------------------------------------


def test_example_contract_loads_with_columns_in_order():
    contract = load_contract(EXAMPLES / "orders.contract.json")

    assert contract.name == "orders"
    assert contract.primary_key == "order_id"
    assert [c.name for c in contract.columns] == [
        "order_id",
        "customer_email",
        "quantity",
        "unit_price",
        "coupon_code",
    ]
    quantity = contract.columns[2]
    assert (quantity.type, quantity.min, quantity.max) == ("integer", 1, 1000)


def test_column_defaults_are_strict():
    contract = parse_contract(minimal())
    assert contract.columns[0] == ColumnRule(
        name="order_id", type="integer", required=True, max_null_fraction=0.0
    )
    assert contract.primary_key is None


def test_number_column_accepts_decimal_bounds():
    contract = parse_contract(
        minimal(columns=[{"name": "price", "type": "number", "min": 0.5, "max": 99.99}])
    )
    assert (contract.columns[0].min, contract.columns[0].max) == (0.5, 99.99)


# --- file-level failures ----------------------------------------------------


def test_missing_file(tmp_path):
    with pytest.raises(ContractError, match="not found"):
        load_contract(tmp_path / "nope.json")


def test_malformed_json_reports_line_number(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text('{\n  "name": "orders",\n  "columns": [\n}\n', encoding="utf-8")
    with pytest.raises(ContractError, match=r"not valid JSON \(line 4"):
        load_contract(path)


def test_duplicate_json_keys_are_rejected(tmp_path):
    path = tmp_path / "dup.json"
    path.write_text('{"contract_version": 1, "name": "a", "name": "b", "columns": []}')
    with pytest.raises(ContractError, match="duplicate JSON key 'name'"):
        load_contract(path)


def test_nan_bound_is_rejected(tmp_path):
    path = tmp_path / "nan.json"
    text = json.dumps(minimal()).replace(
        '"type": "integer"}', '"type": "number", "min": NaN}'
    )
    path.write_text(text)
    with pytest.raises(ContractError, match="NaN is not allowed"):
        load_contract(path)


def test_top_level_must_be_object():
    assert problems_for([1, 2]) == ["top level must be a JSON object, got array"]


# --- contract-level problems ------------------------------------------------


@pytest.mark.parametrize("version", [None, 2, "1", True])
def test_unsupported_versions(version):
    data = minimal(contract_version=version)
    if version is None:
        del data["contract_version"]
    assert len(problems_for(data)) == 1


def test_empty_columns_list():
    assert problems_for(minimal(columns=[])) == ["'columns' must be a non-empty list"]


def test_unknown_top_level_key_catches_typos():
    assert problems_for(minimal(primary_kye="order_id")) == [
        "unknown top-level key 'primary_kye'"
    ]


def test_duplicate_column_names():
    cols = [{"name": "id", "type": "integer"}, {"name": "id", "type": "string"}]
    assert problems_for(minimal(columns=cols)) == ["column 'id' is declared more than once"]


def test_primary_key_must_be_declared():
    assert problems_for(minimal(primary_key="missing")) == [
        "primary_key 'missing' is not a declared column"
    ]


def test_primary_key_cannot_allow_nulls():
    cols = [{"name": "order_id", "type": "integer", "max_null_fraction": 0.1}]
    problems = problems_for(minimal(columns=cols, primary_key="order_id"))
    assert problems == [
        "primary_key column 'order_id' must be required and have max_null_fraction 0"
    ]


def test_all_problems_reported_together():
    data = {
        "contract_version": 9,
        "name": "",
        "columns": [{"name": "qty", "type": "float", "min": True}],
        "extra": 1,
    }
    assert len(problems_for(data)) == 5  # extra, version, name, bad type, min on non-numeric


# --- column-level problems --------------------------------------------------


@pytest.mark.parametrize(
    "column, expected",
    [
        ({"type": "integer"}, "columns[0]: 'name' must be a non-empty string"),
        ({"name": " id", "type": "integer"}, "columns[0]: name ' id' has leading or trailing whitespace"),
        ({"name": "id", "type": "float"}, "column 'id': 'type' must be one of string, integer, number"),
        ({"name": "id", "type": "integer", "nulable": 0.5}, "column 'id': unknown key 'nulable'"),
        ({"name": "id", "type": "integer", "required": "yes"}, "column 'id': 'required' must be true or false"),
        ({"name": "id", "type": "integer", "max_null_fraction": 1.5}, "column 'id': 'max_null_fraction' must be a number from 0 to 1"),
        ({"name": "id", "type": "string", "min": 1}, "column 'id': 'min' is only allowed on integer or number columns"),
        ({"name": "id", "type": "integer", "max": True}, "column 'id': 'max' must be a number"),
        ({"name": "id", "type": "integer", "min": 0.5}, "column 'id': 'min' must be a whole number for an integer column"),
        ({"name": "id", "type": "integer", "min": 10, "max": 1}, "column 'id': 'min' (10) is greater than 'max' (1)"),
    ],
)
def test_invalid_column(column, expected):
    assert problems_for(minimal(columns=[column])) == [expected]


def test_column_entry_must_be_object():
    assert problems_for(minimal(columns=["order_id"])) == [
        "columns[0] must be an object, got string"
    ]


def test_error_message_lists_every_problem():
    error = ContractError(["first problem", "second problem"])
    assert str(error) == "invalid contract:\n  - first problem\n  - second problem"

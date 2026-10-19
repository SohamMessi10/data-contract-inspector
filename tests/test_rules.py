from decimal import Decimal
from pathlib import Path

import pytest

from contract_inspector import (
    ColumnRule,
    DatasetError,
    check_values,
    inspect_dataset,
    load_contract,
    load_dataset,
    parse_contract,
    parse_value,
)

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def make_contract(*columns, primary_key=None):
    data = {"contract_version": 1, "name": "t", "columns": list(columns)}
    if primary_key:
        data["primary_key"] = primary_key
    return parse_contract(data)


def findings_for(tmp_path, contract, text):
    path = tmp_path / "data.csv"
    path.write_text(text, encoding="utf-8")
    dataset, _ = load_dataset(path)
    return check_values(contract, dataset)


# --- acceptance: the documented fixture -------------------------------------


def test_invalid_fixture_produces_exactly_the_documented_findings():
    contract = load_contract(EXAMPLES / "orders.contract.json")
    findings = inspect_dataset(contract, EXAMPLES / "orders_invalid.csv")

    assert [(f.line, f.column, f.rule, f.message) for f in findings] == [
        (3, "quantity", "min", "'0' is below the minimum of 1"),
        (4, "customer_email", "null", "value is null; column allows no nulls (1 of 6 rows null)"),
        (5, "order_id", "duplicate_key", "'1003' duplicates the primary key on line 4"),
        (6, "quantity", "type", "'three' is not an integer"),
        (7, "unit_price", "min", "'-2.00' is below the minimum of 0"),
    ]
    assert {f.severity for f in findings} == {"error"}


def test_valid_fixture_produces_no_findings():
    contract = load_contract(EXAMPLES / "orders.contract.json")
    assert inspect_dataset(contract, EXAMPLES / "orders_valid.csv") == []


def test_same_input_gives_identical_report():
    contract = load_contract(EXAMPLES / "orders.contract.json")
    first = inspect_dataset(contract, EXAMPLES / "orders_invalid.csv")
    assert all(inspect_dataset(contract, EXAMPLES / "orders_invalid.csv") == first for _ in range(3))


def test_unreadable_file_still_raises(tmp_path):
    contract = load_contract(EXAMPLES / "orders.contract.json")
    with pytest.raises(DatasetError):
        inspect_dataset(contract, tmp_path / "missing.csv")


# --- type parsing: no silent coercion ---------------------------------------

INTEGER = ColumnRule(name="n", type="integer")
NUMBER = ColumnRule(name="x", type="number")


@pytest.mark.parametrize("raw, expected", [("0", 0), ("-12", -12), ("007", 7), ("1000000000000000000000", 10**21)])
def test_valid_integers(raw, expected):
    assert parse_value(INTEGER, raw) == expected


@pytest.mark.parametrize("raw", ["1.0", "1e3", " 5", "5 ", "+5", "1,000", "three", "٣", "--1", "-"])
def test_invalid_integers(raw):
    assert parse_value(INTEGER, raw) is None


@pytest.mark.parametrize("raw, expected", [("19.99", Decimal("19.99")), ("-2.00", Decimal("-2")), ("5", Decimal(5))])
def test_valid_numbers(raw, expected):
    assert parse_value(NUMBER, raw) == expected


@pytest.mark.parametrize("raw", ["NaN", "inf", "-Infinity", "1e3", ".5", "5.", " 1.5", "1,5", "$5", "1_000"])
def test_invalid_numbers(raw):
    # Python's float() accepts NaN, inf, 1e3, .5, 5. and 1_000; the contract does not.
    assert parse_value(NUMBER, raw) is None


# --- ranges -----------------------------------------------------------------


def test_bounds_are_inclusive(tmp_path):
    contract = make_contract({"name": "q", "type": "integer", "min": 1, "max": 3})
    findings = findings_for(tmp_path, contract, "q\n0\n1\n3\n4\n")
    assert [(f.line, f.rule) for f in findings] == [(2, "min"), (5, "max")]
    assert findings[1].message == "'4' is above the maximum of 3"


def test_decimal_bound_is_exact(tmp_path):
    # With floats, 0.1 + 0.2 style rounding can make an exact boundary value fail.
    contract = make_contract({"name": "x", "type": "number", "min": 0.1, "max": 0.3})
    findings = findings_for(tmp_path, contract, "x\n0.1\n0.30\n0.3000001\n0.0999\n")
    assert [(f.line, f.rule) for f in findings] == [(4, "max"), (5, "min")]


def test_invalid_type_is_not_also_range_checked(tmp_path):
    contract = make_contract({"name": "q", "type": "integer", "min": 1})
    assert [f.rule for f in findings_for(tmp_path, contract, "q\n-x\n")] == ["type"]


def test_string_columns_accept_any_text(tmp_path):
    contract = make_contract({"name": "s", "type": "string"})
    assert findings_for(tmp_path, contract, "s\nhello\n123\n NaN \n") == []


# --- nulls ------------------------------------------------------------------


def test_whitespace_only_counts_as_null(tmp_path):
    contract = make_contract({"name": "s", "type": "string"})
    findings = findings_for(tmp_path, contract, "s\na\n   \n")
    assert [(f.line, f.rule) for f in findings] == [(3, "null")]


def test_nulls_skip_type_and_range_checks(tmp_path):
    contract = make_contract(
        {"name": "q", "type": "integer", "min": 1, "required": False, "max_null_fraction": 1}
    )
    assert findings_for(tmp_path, contract, "q\n\n\n") == []


def test_null_fraction_within_limit(tmp_path):
    contract = make_contract({"name": "s", "type": "string", "max_null_fraction": 0.5})
    assert findings_for(tmp_path, contract, 's\na\n""\n') == []  # exactly 50% is allowed


def test_null_fraction_over_limit_is_one_column_finding(tmp_path):
    contract = make_contract({"name": "s", "type": "string", "max_null_fraction": 0.25})
    # In a one-column CSV an empty line is skipped as blank, so empty values are written as "".
    [finding] = findings_for(tmp_path, contract, 's\na\n""\n""\nb\n')

    assert (finding.rule, finding.line, finding.column) == ("null_fraction", None, "s")
    assert finding.message == "2 of 4 rows null (50%), above the limit of 25%; null on lines 3, 4"


def test_null_fraction_lists_at_most_five_lines(tmp_path):
    contract = make_contract({"name": "s", "type": "string", "max_null_fraction": 0.1})
    [finding] = findings_for(tmp_path, contract, "s\n" + "\n".join(['""'] * 7) + "\n")
    assert finding.message.endswith("null on lines 2, 3, 4, 5, 6, ...")


def test_header_only_file_has_no_value_findings(tmp_path):
    contract = make_contract({"name": "s", "type": "string", "max_null_fraction": 0.5})
    assert findings_for(tmp_path, contract, "s\n") == []  # no rows: no division by zero


# --- primary key ------------------------------------------------------------


def test_duplicate_key_points_at_first_occurrence(tmp_path):
    contract = make_contract({"name": "id", "type": "integer"}, primary_key="id")
    findings = findings_for(tmp_path, contract, "id\n1\n2\n1\n1\n")
    assert [(f.line, f.message) for f in findings] == [
        (4, "'1' duplicates the primary key on line 2"),
        (5, "'1' duplicates the primary key on line 2"),
    ]


def test_integer_keys_compare_by_value(tmp_path):
    contract = make_contract({"name": "id", "type": "integer"}, primary_key="id")
    [finding] = findings_for(tmp_path, contract, "id\n1003\n01003\n")
    assert finding.message == "'01003' duplicates the primary key on line 2"


def test_string_keys_are_case_sensitive(tmp_path):
    contract = make_contract({"name": "code", "type": "string"}, primary_key="code")
    assert findings_for(tmp_path, contract, "code\nabc\nABC\n") == []


def test_non_key_duplicates_are_allowed(tmp_path):
    contract = make_contract({"name": "id", "type": "integer"}, {"name": "q", "type": "integer"}, primary_key="id")
    assert findings_for(tmp_path, contract, "id,q\n1,5\n2,5\n") == []


# --- interaction with structural checks -------------------------------------


def test_missing_column_is_reported_once_not_per_row(tmp_path):
    contract = make_contract({"name": "id", "type": "integer"}, {"name": "email", "type": "string"})
    path = tmp_path / "data.csv"
    path.write_text("id\n1\n2\n", encoding="utf-8")
    assert [f.rule for f in inspect_dataset(contract, path)] == ["missing_column"]


def test_findings_are_sorted_by_line_then_contract_column_order(tmp_path):
    contract = make_contract(
        {"name": "a", "type": "integer"}, {"name": "b", "type": "integer"}, primary_key="a"
    )
    path = tmp_path / "data.csv"
    path.write_text("b,a,extra\nx,1,\n2,1,\n3\n", encoding="utf-8")
    assert [(f.line, f.column, f.rule) for f in inspect_dataset(contract, path)] == [
        (2, "b", "type"),
        (3, "a", "duplicate_key"),
        (4, None, "field_count"),
        (None, "extra", "unexpected_column"),
    ]

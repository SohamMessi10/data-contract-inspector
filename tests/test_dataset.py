from pathlib import Path

import pytest

from contract_inspector import DatasetError, check_columns, load_contract, load_dataset, parse_contract

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def write(tmp_path, text, name="data.csv", encoding="utf-8"):
    path = tmp_path / name
    path.write_bytes(text.encode(encoding))
    return path


def contract_with(*columns):
    return parse_contract({"contract_version": 1, "name": "t", "columns": list(columns)})


# --- reading valid files ----------------------------------------------------


def test_example_file_rows_and_line_numbers():
    dataset, findings = load_dataset(EXAMPLES / "orders_invalid.csv")

    assert findings == []
    assert dataset.header[0] == "order_id"
    assert [row.line for row in dataset.rows] == [2, 3, 4, 5, 6, 7]
    assert dataset.rows[2].values == ("1003", "", "1", "12.50", "")


def test_values_are_kept_as_raw_text(tmp_path):
    # Type conversion is a later, explicit step; the loader must not coerce.
    dataset, _ = load_dataset(write(tmp_path, "id,price\n007, 1.50\n"))
    assert dataset.rows[0].values == ("007", " 1.50")


def test_quoted_comma_and_multiline_field_keep_correct_line_numbers(tmp_path):
    text = 'id,note\n1,"a, b"\n2,"line one\nline two"\n3,plain\n'
    dataset, findings = load_dataset(write(tmp_path, text))

    assert findings == []
    assert [row.values for row in dataset.rows] == [
        ("1", "a, b"),
        ("2", "line one\nline two"),
        ("3", "plain"),
    ]
    assert [row.line for row in dataset.rows] == [2, 3, 5]  # row 3 starts after the 2-line field


def test_excel_byte_order_mark_is_removed_from_header(tmp_path):
    dataset, _ = load_dataset(write(tmp_path, "﻿id,name\n1,a\n"))
    assert dataset.header == ("id", "name")


def test_windows_line_endings(tmp_path):
    dataset, _ = load_dataset(write(tmp_path, "id,name\r\n1,a\r\n2,b\r\n"))
    assert [row.values for row in dataset.rows] == [("1", "a"), ("2", "b")]


def test_blank_lines_are_skipped_but_line_numbers_stay_true(tmp_path):
    dataset, findings = load_dataset(write(tmp_path, "id\n1\n\n2\n\n"))
    assert findings == []
    assert [(row.line, row.values) for row in dataset.rows] == [(2, ("1",)), (4, ("2",))]


def test_header_only_file_has_no_rows(tmp_path):
    dataset, findings = load_dataset(write(tmp_path, "id,name\n"))
    assert dataset.rows == () and findings == []


# --- structural findings ----------------------------------------------------


def test_rows_with_wrong_field_count_are_reported_and_excluded(tmp_path):
    dataset, findings = load_dataset(write(tmp_path, "a,b\n1,2\n3\n4,5,6\n7,8\n"))

    assert [row.line for row in dataset.rows] == [2, 5]
    assert [(f.rule, f.line) for f in findings] == [("field_count", 3), ("field_count", 4)]
    assert findings[0].message == (
        "row has 1 fields but the header has 2; row was not checked further"
    )


# --- unreadable files -------------------------------------------------------


@pytest.mark.parametrize(
    "text, expected",
    [
        ("", "is empty or its first line is blank"),
        ("\nid\n1\n", "is empty or its first line is blank"),
        ("id,,name\n", "header column 2 has no name"),
        ("id,name,id\n", "names column 'id' more than once"),
        ('id,note\n1,"unclosed\n2,x\n', r"is not a readable CSV \(line 3\)"),
        ("id\n" + "x" * 200_000 + "\n", "field larger than field limit"),
    ],
    ids=["empty", "blank-first-line", "unnamed-column", "duplicate-header", "unclosed-quote", "huge-field"],
)
def test_unreadable_contents(tmp_path, text, expected):
    with pytest.raises(DatasetError, match=expected):
        load_dataset(write(tmp_path, text))


def test_missing_file(tmp_path):
    with pytest.raises(DatasetError, match="not found"):
        load_dataset(tmp_path / "nope.csv")


def test_directory_instead_of_file(tmp_path):
    with pytest.raises(DatasetError, match="is a directory"):
        load_dataset(tmp_path)


def test_non_utf8_file(tmp_path):
    path = write(tmp_path, "id,city\n1,Montréal\n", encoding="latin-1")
    with pytest.raises(DatasetError, match="not valid UTF-8"):
        load_dataset(path)


# --- header vs contract -----------------------------------------------------


def test_example_files_match_the_example_contract():
    contract = load_contract(EXAMPLES / "orders.contract.json")
    for name in ("orders_valid.csv", "orders_invalid.csv"):
        dataset, _ = load_dataset(EXAMPLES / name)
        assert check_columns(contract, dataset) == []


def test_missing_required_column(tmp_path):
    contract = contract_with({"name": "id", "type": "integer"}, {"name": "email", "type": "string"})
    dataset, _ = load_dataset(write(tmp_path, "id\n1\n"))

    [finding] = check_columns(contract, dataset)
    assert (finding.severity, finding.rule, finding.column) == ("error", "missing_column", "email")
    assert finding.message == "required column 'email' is missing"


def test_missing_optional_column_is_fine(tmp_path):
    contract = contract_with(
        {"name": "id", "type": "integer"},
        {"name": "coupon", "type": "string", "required": False, "max_null_fraction": 1},
    )
    dataset, _ = load_dataset(write(tmp_path, "id\n1\n"))
    assert check_columns(contract, dataset) == []


def test_whitespace_in_header_is_reported_not_silently_fixed(tmp_path):
    contract = contract_with({"name": "quantity", "type": "integer"})
    dataset, _ = load_dataset(write(tmp_path, " quantity\n1\n"))

    messages = [f.message for f in check_columns(contract, dataset)]
    assert messages == [
        "required column 'quantity' is missing "
        "(the header has ' quantity', which includes extra whitespace)",
        "column ' quantity' is not in the contract and was not checked",
    ]


def test_header_match_is_case_sensitive(tmp_path):
    contract = contract_with({"name": "id", "type": "integer"})
    dataset, _ = load_dataset(write(tmp_path, "ID\n1\n"))
    assert [f.rule for f in check_columns(contract, dataset)] == ["missing_column", "unexpected_column"]


def test_extra_column_is_a_warning(tmp_path):
    contract = contract_with({"name": "id", "type": "integer"})
    dataset, _ = load_dataset(write(tmp_path, "id,notes\n1,x\n"))

    [finding] = check_columns(contract, dataset)
    assert (finding.severity, finding.rule, finding.column) == ("warning", "unexpected_column", "notes")

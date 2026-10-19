import json
from pathlib import Path

import pytest

from contract_inspector import (
    build_report,
    format_summary,
    inspect,
    load_contract,
    parse_contract,
    to_json,
    write_report,
)
from contract_inspector import report as report_module

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


@pytest.fixture
def orders_contract():
    return load_contract(EXAMPLES / "orders.contract.json")


def report_for(contract, path, label=None):
    return build_report(contract, inspect(contract, path), label or str(path))


def csv_file(tmp_path, text):
    path = tmp_path / "data.csv"
    path.write_text(text, encoding="utf-8")
    return path


# --- golden file ------------------------------------------------------------


def test_invalid_fixture_matches_golden_report(orders_contract):
    # If this fails after an intended format change, regenerate the golden file and
    # review its diff in Git before committing.
    report = report_for(orders_contract, EXAMPLES / "orders_invalid.csv", "examples/orders_invalid.csv")
    golden = (EXAMPLES / "orders_invalid.report.json").read_text(encoding="utf-8")
    assert to_json(report) == golden


def test_report_is_byte_identical_across_runs(orders_contract):
    outputs = {
        to_json(report_for(orders_contract, EXAMPLES / "orders_invalid.csv", "x.csv")) for _ in range(3)
    }
    assert len(outputs) == 1


def test_report_contains_no_absolute_path(orders_contract):
    text = to_json(report_for(orders_contract, EXAMPLES / "orders_invalid.csv", "orders_invalid.csv"))
    assert str(EXAMPLES) not in text


# --- content ----------------------------------------------------------------


def test_valid_fixture_passes_with_empty_findings(orders_contract):
    report = report_for(orders_contract, EXAMPLES / "orders_valid.csv")
    assert report["status"] == "pass"
    assert report["findings"] == []
    assert report["summary"] == {
        "rows_checked": 5,
        "rows_skipped": 0,
        "errors": 0,
        "warnings": 0,
        "by_rule": {},
    }


def test_warnings_alone_do_not_fail(tmp_path):
    contract = parse_contract({"contract_version": 1, "name": "t", "columns": [{"name": "id", "type": "integer"}]})
    report = report_for(contract, csv_file(tmp_path, "id,notes\n1,x\n"))
    assert report["status"] == "pass"
    assert report["summary"]["warnings"] == 1


def test_skipped_rows_are_counted_separately(tmp_path):
    contract = parse_contract({"contract_version": 1, "name": "t", "columns": [{"name": "a", "type": "string"}, {"name": "b", "type": "string"}]})
    report = report_for(contract, csv_file(tmp_path, "a,b\n1,2\n3\n4,5\n"))
    assert (report["summary"]["rows_checked"], report["summary"]["rows_skipped"]) == (2, 1)
    assert report["status"] == "fail"


def test_file_wide_finding_has_null_line_in_json(tmp_path):
    contract = parse_contract({"contract_version": 1, "name": "t", "columns": [{"name": "id", "type": "integer"}]})
    report = report_for(contract, csv_file(tmp_path, "id,extra\n1,x\n"))
    assert json.loads(to_json(report))["findings"][0]["line"] is None


def test_non_ascii_text_stays_readable(tmp_path):
    contract = parse_contract({"contract_version": 1, "name": "villes", "columns": [{"name": "id", "type": "integer"}]})
    text = to_json(report_for(contract, csv_file(tmp_path, "id\nMontréal\n")))
    assert "'Montréal' is not an integer" in text


# --- atomic writing ---------------------------------------------------------


def test_write_report_round_trips(orders_contract, tmp_path):
    report = report_for(orders_contract, EXAMPLES / "orders_invalid.csv", "orders_invalid.csv")
    target = tmp_path / "report.json"
    write_report(report, target)
    assert json.loads(target.read_text(encoding="utf-8")) == report
    assert [p.name for p in tmp_path.iterdir()] == ["report.json"]  # no temp file left behind


def test_failed_write_keeps_old_report_and_cleans_up(orders_contract, tmp_path, monkeypatch):
    target = tmp_path / "report.json"
    target.write_text("old report\n", encoding="utf-8")

    def crash(_report):
        raise RuntimeError("simulated crash while serializing")

    monkeypatch.setattr(report_module, "to_json", crash)
    report = report_for(orders_contract, EXAMPLES / "orders_valid.csv")
    with pytest.raises(RuntimeError):
        write_report(report, target)

    assert target.read_text(encoding="utf-8") == "old report\n"
    assert [p.name for p in tmp_path.iterdir()] == ["report.json"]


def test_write_to_missing_directory_raises(orders_contract, tmp_path):
    report = report_for(orders_contract, EXAMPLES / "orders_valid.csv")
    with pytest.raises(FileNotFoundError):
        write_report(report, tmp_path / "no-such-dir" / "report.json")


# --- terminal summary -------------------------------------------------------


def test_summary_for_invalid_fixture(orders_contract):
    report = report_for(orders_contract, EXAMPLES / "orders_invalid.csv", "orders_invalid.csv")
    lines = format_summary(report).splitlines()
    assert lines[0] == "FAIL: orders_invalid.csv against contract 'orders'"
    assert lines[1] == "6 rows checked, 0 skipped, 5 errors, 0 warnings"
    assert lines[3] == "  error    line 3 [quantity]: '0' is below the minimum of 1"
    assert len(lines) == 8


def test_summary_uses_singular_and_file_label(tmp_path):
    contract = parse_contract({"contract_version": 1, "name": "t", "columns": [{"name": "id", "type": "integer"}]})
    report = report_for(contract, csv_file(tmp_path, "id,extra\nx,1\n"), "d.csv")
    assert format_summary(report).splitlines()[1:] == [
        "1 rows checked, 0 skipped, 1 error, 1 warning",
        "",
        "  error    line 2 [id]: 'x' is not an integer",
        "  warning  file [extra]: column 'extra' is not in the contract and was not checked",
    ]


def test_summary_truncates_long_lists(tmp_path):
    contract = parse_contract({"contract_version": 1, "name": "t", "columns": [{"name": "id", "type": "integer"}]})
    path = csv_file(tmp_path, "id\n" + "x\n" * 25)
    lines = format_summary(report_for(contract, path), max_findings=20).splitlines()
    assert lines[-1] == "  ... and 5 more (see the JSON report for all findings)"
    assert len(lines) == 3 + 20 + 1

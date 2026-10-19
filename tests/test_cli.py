import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from contract_inspector.cli import ExitCode, main

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


@pytest.fixture
def work(tmp_path, monkeypatch):
    """A temp directory holding copies of the examples, used as the working directory."""
    for name in ("orders.contract.json", "orders_valid.csv", "orders_invalid.csv"):
        shutil.copy(EXAMPLES / name, tmp_path / name)
    monkeypatch.chdir(tmp_path)
    return tmp_path


def run(capsys, *args):
    code = main(list(args))
    out, err = capsys.readouterr()
    return code, out, err


# --- exit codes -------------------------------------------------------------


def test_valid_dataset_exits_0(work, capsys):
    code, out, err = run(capsys, "check", "orders_valid.csv", "--contract", "orders.contract.json")
    assert code == ExitCode.PASS == 0
    assert out.startswith("PASS: orders_valid.csv against contract 'orders'")
    assert err == ""


def test_violations_exit_1_and_list_findings(work, capsys):
    code, out, err = run(capsys, "check", "orders_invalid.csv", "-c", "orders.contract.json")
    assert code == ExitCode.VIOLATIONS == 1
    assert "5 errors" in out
    assert "line 6 [quantity]: 'three' is not an integer" in out
    assert err == ""


def test_warnings_only_exit_0(work, capsys):
    header, *rows = (work / "orders_valid.csv").read_text(encoding="utf-8").splitlines()
    lines = [header + ",notes"] + [row + ",x" for row in rows]  # one column the contract doesn't know
    (work / "extra.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    code, out, _ = run(capsys, "check", "extra.csv", "-c", "orders.contract.json")
    assert code == 0
    assert "1 warning" in out


def test_invalid_contract_exits_2_with_every_problem_on_stderr(work, capsys):
    (work / "bad.json").write_text('{"contract_version": 1, "name": "x", "columns": [{"name": "q", "type": "float", "mxa": 1}]}')
    code, out, err = run(capsys, "check", "orders_valid.csv", "-c", "bad.json")
    assert code == ExitCode.USAGE_OR_CONTRACT == 2
    assert out == ""
    assert "unknown key 'mxa'" in err and "'type' must be one of" in err


def test_missing_contract_exits_2(work, capsys):
    code, _, err = run(capsys, "check", "orders_valid.csv", "-c", "nope.json")
    assert code == 2
    assert "contract file not found: nope.json" in err


def test_missing_arguments_exit_2(work, capsys):
    with pytest.raises(SystemExit) as exc:
        main(["check", "orders_valid.csv"])
    assert exc.value.code == 2
    assert "--contract" in capsys.readouterr().err


def test_unknown_command_exits_2(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["validate", "x.csv"])
    assert exc.value.code == 2


@pytest.mark.parametrize("value", ["0", "-3", "ten"])
def test_bad_max_findings_exits_2(work, capsys, value):
    with pytest.raises(SystemExit) as exc:
        main(["check", "orders_valid.csv", "-c", "orders.contract.json", "--max-findings", value])
    assert exc.value.code == 2


def test_missing_dataset_exits_3(work, capsys):
    code, out, err = run(capsys, "check", "missing.csv", "-c", "orders.contract.json")
    assert code == ExitCode.DATASET_UNREADABLE == 3
    assert out == ""
    assert err == "contract-inspector: error: cannot check dataset: dataset file not found: missing.csv\n"


def test_unreadable_dataset_exits_3(work, capsys):
    (work / "latin1.csv").write_bytes("order_id\n1,Montréal\n".encode("latin-1"))
    code, _, err = run(capsys, "check", "latin1.csv", "-c", "orders.contract.json")
    assert code == 3
    assert "not valid UTF-8" in err


def test_contract_is_checked_before_dataset(work, capsys):
    # Both are broken: the contract error wins, because without a valid contract nothing can run.
    code, _, _ = run(capsys, "check", "missing.csv", "-c", "nope.json")
    assert code == 2


# --- report output ----------------------------------------------------------


def test_report_file_is_written_even_when_dataset_fails(work, capsys):
    code, out, _ = run(capsys, "check", "orders_invalid.csv", "-c", "orders.contract.json", "--report", "out.json")
    assert code == 1
    assert out.rstrip().endswith("report written to out.json")
    report = json.loads((work / "out.json").read_text(encoding="utf-8"))
    assert report["status"] == "fail"
    assert report["dataset"] == "orders_invalid.csv"


def test_report_matches_golden_file(work, capsys):
    # The golden file names the dataset "examples/orders_invalid.csv", so mirror that path.
    (work / "examples").mkdir()
    shutil.copy(EXAMPLES / "orders_invalid.csv", work / "examples" / "orders_invalid.csv")
    run(capsys, "check", "examples/orders_invalid.csv", "-c", "orders.contract.json", "-r", "out.json")
    golden = (EXAMPLES / "orders_invalid.report.json").read_text(encoding="utf-8")
    assert (work / "out.json").read_text(encoding="utf-8") == golden


def test_json_flag_prints_only_json(work, capsys):
    code, out, err = run(capsys, "check", "orders_invalid.csv", "-c", "orders.contract.json", "--json")
    assert code == 1
    assert json.loads(out)["summary"]["errors"] == 5  # stdout is pure JSON, safe to pipe
    assert err == ""


def test_no_report_written_when_dataset_unreadable(work, capsys):
    code, _, _ = run(capsys, "check", "missing.csv", "-c", "orders.contract.json", "-r", "out.json")
    assert code == 3
    assert not (work / "out.json").exists()


def test_report_to_missing_directory_exits_4(work, capsys):
    code, out, err = run(capsys, "check", "orders_valid.csv", "-c", "orders.contract.json", "-r", "nodir/out.json")
    assert code == ExitCode.REPORT_NOT_WRITTEN == 4
    assert out.startswith("PASS")  # the checks still ran and were shown
    assert "report could not be written to nodir/out.json" in err


@pytest.mark.parametrize("target", ["orders_valid.csv", "./orders_valid.csv", "orders.contract.json"])
def test_refuses_to_overwrite_an_input_file(work, capsys, target):
    before = (work / "orders_valid.csv").read_bytes(), (work / "orders.contract.json").read_bytes()
    code, out, err = run(capsys, "check", "orders_valid.csv", "-c", "orders.contract.json", "-r", target)
    assert code == 2
    assert out == ""
    assert "is one of the input files" in err
    assert ((work / "orders_valid.csv").read_bytes(), (work / "orders.contract.json").read_bytes()) == before


def test_max_findings_truncates_summary(work, capsys):
    _, out, _ = run(capsys, "check", "orders_invalid.csv", "-c", "orders.contract.json", "--max-findings", "2")
    assert "... and 3 more (see the JSON report for all findings)" in out


# --- the real command, end to end -------------------------------------------


def test_python_dash_m_runs_end_to_end(work):
    result = subprocess.run(
        [sys.executable, "-m", "contract_inspector", "check", "orders_invalid.csv", "-c", "orders.contract.json"],
        capture_output=True,
        text=True,
        cwd=work,
    )
    assert result.returncode == 1
    assert result.stdout.startswith("FAIL: orders_invalid.csv")
    assert result.stderr == ""


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert capsys.readouterr().out.strip() == "contract-inspector 0.1.0"

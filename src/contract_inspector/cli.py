"""Command-line interface.

    contract-inspector check DATA.csv --contract CONTRACT.json [--report OUT.json] [--json]

Results go to stdout; problems running the tool go to stderr. The exit code is
the machine-readable answer, so a shell script or CI job can act on it without
parsing any text.
"""

from __future__ import annotations

import argparse
import sys
from enum import IntEnum
from pathlib import Path
from typing import Sequence

from contract_inspector import __version__
from contract_inspector.contract import ContractError, load_contract
from contract_inspector.dataset import DatasetError
from contract_inspector.report import build_report, format_summary, to_json, write_report
from contract_inspector.rules import inspect


class ExitCode(IntEnum):
    PASS = 0  # dataset satisfies the contract (warnings allowed)
    VIOLATIONS = 1  # dataset was read but breaks the contract
    USAGE_OR_CONTRACT = 2  # bad arguments or an invalid contract (argparse also uses 2)
    DATASET_UNREADABLE = 3  # dataset could not be read, so nothing was checked
    REPORT_NOT_WRITTEN = 4  # checks ran, but the --report file could not be written


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="contract-inspector",
        description="Check a CSV file against a data contract.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    check = commands.add_parser(
        "check",
        help="check a CSV file against a contract",
        description="Check a CSV file against a contract.",
        epilog=(
            "exit codes: 0 pass, 1 contract violations, 2 usage or contract error, "
            "3 dataset unreadable, 4 report file not written"
        ),
    )
    check.add_argument("dataset", metavar="DATA", help="path to the CSV file")
    check.add_argument("--contract", "-c", required=True, metavar="CONTRACT", help="path to the contract JSON file")
    check.add_argument("--report", "-r", metavar="OUT", help="also write the full JSON report to this file")
    check.add_argument(
        "--json",
        action="store_true",
        help="print the JSON report to stdout instead of the text summary",
    )
    check.add_argument(
        "--max-findings",
        type=_positive_int,
        default=20,
        metavar="N",
        help="findings to show in the text summary (default: 20)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)  # exits with code 2 on bad arguments
    return _check(args)


def _check(args: argparse.Namespace) -> int:
    if args.report and _same_file(args.report, args.dataset, args.contract):
        # A typo such as `--report data.csv` would otherwise replace the input with JSON.
        _error(f"--report {args.report} is one of the input files; choose a different output path")
        return ExitCode.USAGE_OR_CONTRACT

    try:
        contract = load_contract(args.contract)
    except ContractError as exc:
        _error(str(exc))
        return ExitCode.USAGE_OR_CONTRACT

    try:
        inspection = inspect(contract, args.dataset)
    except DatasetError as exc:
        _error(f"cannot check dataset: {exc}")
        return ExitCode.DATASET_UNREADABLE

    report = build_report(contract, inspection, dataset_label=args.dataset)
    if args.json:
        sys.stdout.write(to_json(report))
    else:
        print(format_summary(report, max_findings=args.max_findings))

    if args.report:
        try:
            write_report(report, args.report)
        except OSError as exc:
            _error(f"checks ran, but the report could not be written to {args.report}: {exc.strerror or exc}")
            return ExitCode.REPORT_NOT_WRITTEN
        if not args.json:
            print(f"\nreport written to {args.report}")

    return ExitCode.VIOLATIONS if report["status"] == "fail" else ExitCode.PASS


def _same_file(output: str, *inputs: str) -> bool:
    out = Path(output).resolve()  # resolve() follows symlinks and "..", so aliases match too
    return any(out == Path(path).resolve() for path in inputs)


def _positive_int(text: str) -> int:
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected a whole number, got {text!r}") from None
    if value < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return value


def _error(message: str) -> None:
    print(f"contract-inspector: error: {message}", file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main())

"""Turn an inspection into a JSON report and a short terminal summary.

The report is deterministic: no timestamps, no absolute paths, fixed key and
finding order. Running the same contract on the same file always produces the
same bytes, so reports can be diffed, cached, or committed as test fixtures.
"""

from __future__ import annotations

import json
import os
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

from contract_inspector.contract import Contract
from contract_inspector.rules import Inspection

REPORT_VERSION = 1


def build_report(contract: Contract, inspection: Inspection, dataset_label: str) -> dict[str, Any]:
    """Build the report as plain JSON-compatible data.

    `dataset_label` is how the dataset is named in the report (usually the path
    the user typed). It is passed in, not derived, so the report never leaks an
    absolute path such as /Users/<name>/... unless the user asked for one.
    """
    findings = inspection.findings
    severities = Counter(f.severity for f in findings)
    skipped = sum(1 for f in findings if f.rule == "field_count")
    return {
        "report_version": REPORT_VERSION,
        "contract": contract.name,
        "dataset": dataset_label,
        # Warnings (such as an extra column) are worth reading but do not fail a dataset.
        "status": "fail" if severities["error"] else "pass",
        "summary": {
            "rows_checked": len(inspection.dataset.rows),
            "rows_skipped": skipped,
            "errors": severities["error"],
            "warnings": severities["warning"],
            "by_rule": dict(sorted(Counter(f.rule for f in findings).items())),
        },
        "findings": [
            {
                "severity": f.severity,
                "rule": f.rule,
                "line": f.line,
                "column": f.column,
                "message": f.message,
            }
            for f in findings
        ],
    }


def to_json(report: dict[str, Any]) -> str:
    # ensure_ascii=False keeps names like "Montréal" readable; the file is written as UTF-8.
    return json.dumps(report, indent=2, ensure_ascii=False) + "\n"


def write_report(report: dict[str, Any], path: str | Path) -> None:
    """Write the report atomically: readers see the old file or the complete new one.

    The JSON goes to a temporary file in the same directory, which is then renamed
    over the target. A rename within one filesystem is atomic, so a crash halfway
    through never leaves a truncated report for a pipeline to misread.
    """
    path = Path(path)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(to_json(report))
        os.replace(tmp_name, path)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise


def format_summary(report: dict[str, Any], max_findings: int = 20) -> str:
    """Human-readable summary for the terminal."""
    summary = report["summary"]
    lines = [
        f"{report['status'].upper()}: {report['dataset']} against contract {report['contract']!r}",
        f"{summary['rows_checked']} rows checked, {summary['rows_skipped']} skipped, "
        f"{_plural(summary['errors'], 'error')}, {_plural(summary['warnings'], 'warning')}",
    ]
    findings = report["findings"]
    if findings:
        lines.append("")
    for item in findings[:max_findings]:
        where = f"line {item['line']}" if item["line"] is not None else "file"
        column = f" [{item['column']}]" if item["column"] else ""
        lines.append(f"  {item['severity']:7}  {where}{column}: {item['message']}")
    hidden = len(findings) - max_findings
    if hidden > 0:
        lines.append(f"  ... and {hidden} more (see the JSON report for all findings)")
    return "\n".join(lines)


def _plural(count: int, word: str) -> str:
    return f"{count} {word}" if count == 1 else f"{count} {word}s"

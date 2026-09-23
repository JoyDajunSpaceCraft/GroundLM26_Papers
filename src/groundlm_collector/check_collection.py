"""Incremental batch execution of ACL publication checks."""

from __future__ import annotations

from collections.abc import Callable, Sequence
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import io
from pathlib import Path

from .pubcheck import PubcheckResult, run_pubcheck
from .storage import atomic_write_bytes


Checker = Callable[[Path, str, Sequence[str]], PubcheckResult]
COMPLETED_STATUSES = {"pass", "fail", "error", "needs_review"}
REQUIRED_COLUMNS = {
    "number",
    "title",
    "paper_type",
    "pdf_path",
    "aclpubcheck_status",
    "aclpubcheck_summary",
    "aclpubcheck_pdf_sha256",
    "checked_at_utc",
}


@dataclass(frozen=True, slots=True)
class BatchCheckSummary:
    total: int
    checked: int
    skipped: int
    passed: int
    failed: int
    errors: int
    needs_review: int


def check_collection(
    csv_path: Path,
    project_root: Path,
    logs_dir: Path,
    *,
    force: bool = False,
    executable: Sequence[str] = ("aclpubcheck",),
    checker: Checker = run_pubcheck,
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> BatchCheckSummary:
    with csv_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or ())
        rows = list(reader)
    missing_columns = sorted(REQUIRED_COLUMNS.difference(fieldnames))
    if missing_columns:
        raise ValueError(
            "papers.csv is missing required columns: " + ", ".join(missing_columns)
        )

    logs_dir.mkdir(parents=True, exist_ok=True)
    counts = {"pass": 0, "fail": 0, "error": 0, "needs_review": 0}
    checked = 0
    skipped = 0
    for row in rows:
        pdf_path = project_root / row["pdf_path"]
        try:
            digest = _sha256(pdf_path)
        except FileNotFoundError:
            message = f"PDF not found: {row['pdf_path']}"
            result = PubcheckResult(
                status="error",
                exit_code=None,
                summary=message,
                output=message,
                command_version=" ".join(executable),
            )
            digest = ""
        except OSError as error:
            message = f"Could not read PDF {row['pdf_path']}: {error}"
            result = PubcheckResult(
                status="error",
                exit_code=None,
                summary=message,
                output=message,
                command_version=" ".join(executable),
            )
            digest = ""
        else:
            result = None
        if (
            result is None
            and not force
            and row["aclpubcheck_pdf_sha256"] == digest
            and row["aclpubcheck_status"] in COMPLETED_STATUSES
        ):
            skipped += 1
            continue
        if result is None:
            result = checker(pdf_path, row["paper_type"], executable)
        row["aclpubcheck_status"] = result.status
        row["aclpubcheck_summary"] = result.summary
        row["aclpubcheck_pdf_sha256"] = digest
        row["checked_at_utc"] = _format_utc(now())
        counts[result.status] += 1
        checked += 1
        _write_log(logs_dir / f"{row['number']}.log", row, result)

    if checked:
        _write_rows(csv_path, fieldnames, rows)
    return BatchCheckSummary(
        total=len(rows),
        checked=checked,
        skipped=skipped,
        passed=counts["pass"],
        failed=counts["fail"],
        errors=counts["error"],
        needs_review=counts["needs_review"],
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _format_utc(value: datetime) -> str:
    normalized = value.astimezone(timezone.utc).replace(microsecond=0)
    return normalized.isoformat().replace("+00:00", "Z")


def _write_log(path: Path, row: dict[str, str], result: PubcheckResult) -> None:
    body = (
        f"paper: {row['number']}\n"
        f"title: {row['title']}\n"
        f"status: {result.status}\n"
        f"exit_code: {result.exit_code}\n"
        f"command: {result.command_version}\n\n"
        f"{result.output.rstrip()}\n"
    )
    atomic_write_bytes(path, body.encode("utf-8"))


def _write_rows(
    csv_path: Path, fieldnames: list[str], rows: list[dict[str, str]]
) -> None:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(
        buffer,
        fieldnames=fieldnames,
        lineterminator="\n",
        quoting=csv.QUOTE_MINIMAL,
    )
    writer.writeheader()
    writer.writerows(rows)
    atomic_write_bytes(csv_path, buffer.getvalue().encode("utf-8"))

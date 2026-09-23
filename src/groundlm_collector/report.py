"""GitHub-readable CSV reporting for collected papers."""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
import io
from pathlib import Path

from .storage import atomic_write_bytes


CSV_COLUMNS = (
    "number",
    "title",
    "authors",
    "source_venue",
    "track",
    "openreview_submission_number",
    "decision",
    "archival_status",
    "paper_type",
    "aclpubcheck_status",
    "aclpubcheck_summary",
    "openreview_url",
    "pdf_path",
    "supplementary_files",
    "aclpubcheck_pdf_sha256",
    "checked_at_utc",
)


@dataclass(frozen=True, slots=True)
class PaperRow:
    number: str
    title: str
    authors: tuple[str, ...]
    source_venue: str
    track: str
    openreview_submission_number: int
    decision: str
    archival_status: str
    paper_type: str
    aclpubcheck_status: str
    aclpubcheck_summary: str
    openreview_url: str
    pdf_path: str
    supplementary_files: tuple[str, ...]
    aclpubcheck_pdf_sha256: str
    checked_at_utc: str


def write_csv(path: Path, rows: list[PaperRow]) -> None:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(
        buffer,
        fieldnames=CSV_COLUMNS,
        lineterminator="\n",
        quoting=csv.QUOTE_MINIMAL,
    )
    writer.writeheader()
    for row in rows:
        values = asdict(row)
        values["authors"] = "; ".join(row.authors)
        values["supplementary_files"] = "; ".join(row.supplementary_files)
        writer.writerow(values)
    atomic_write_bytes(path, buffer.getvalue().encode("utf-8"))

import csv
from datetime import datetime, timezone
import hashlib

import pytest

from groundlm_collector.check_collection import check_collection
from groundlm_collector.pubcheck import PubcheckResult
from groundlm_collector.report import PaperRow, write_csv


FIXED_NOW = datetime(2026, 9, 23, 15, 30, tzinfo=timezone.utc)


def make_collection(tmp_path, **overrides):
    pdf_path = tmp_path / "all_papers/001/paper.pdf"
    pdf_path.parent.mkdir(parents=True)
    pdf_path.write_bytes(b"%PDF-test-paper")
    values = {
        "number": "001",
        "title": "Test Paper",
        "authors": ("Alice",),
        "source_venue": "GroundLM",
        "track": "Track 1: Direct Submission",
        "openreview_submission_number": 1,
        "decision": "Accept",
        "archival_status": "archival",
        "paper_type": "long",
        "aclpubcheck_status": "pending",
        "aclpubcheck_summary": "Not run",
        "openreview_url": "https://openreview.net/forum?id=test",
        "pdf_path": "all_papers/001/paper.pdf",
        "supplementary_files": (),
        "aclpubcheck_pdf_sha256": "",
        "checked_at_utc": "",
    }
    values.update(overrides)
    csv_path = tmp_path / "papers.csv"
    write_csv(csv_path, [PaperRow(**values)])
    return csv_path, pdf_path


def read_row(csv_path):
    with csv_path.open(encoding="utf-8", newline="") as handle:
        return next(csv.DictReader(handle))


def read_rows(csv_path):
    with csv_path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_checks_unseen_pdf_and_records_result(tmp_path):
    csv_path, pdf_path = make_collection(tmp_path)
    calls = []

    def checker(pdf, paper_type, executable):
        calls.append((pdf, paper_type, tuple(executable)))
        return PubcheckResult(
            status="pass",
            exit_code=0,
            summary="All checks passed",
            output="Detailed successful output",
            command_version="aclpubcheck",
        )

    summary = check_collection(
        csv_path,
        project_root=tmp_path,
        logs_dir=tmp_path / "logs",
        executable=("aclpubcheck",),
        checker=checker,
        now=lambda: FIXED_NOW,
    )

    row = read_row(csv_path)
    assert calls == [(pdf_path, "long", ("aclpubcheck",))]
    assert row["aclpubcheck_status"] == "pass"
    assert row["aclpubcheck_summary"] == "All checks passed"
    assert row["aclpubcheck_pdf_sha256"] == hashlib.sha256(
        pdf_path.read_bytes()
    ).hexdigest()
    assert row["checked_at_utc"] == "2026-09-23T15:30:00Z"
    assert (tmp_path / "logs/001.log").read_text(encoding="utf-8").endswith(
        "Detailed successful output\n"
    )
    assert summary.total == 1
    assert summary.checked == 1
    assert summary.skipped == 0
    assert summary.passed == 1


def test_skips_unchanged_completed_pdf_without_rewriting_csv(tmp_path):
    digest = hashlib.sha256(b"%PDF-test-paper").hexdigest()
    csv_path, _ = make_collection(
        tmp_path,
        aclpubcheck_status="pass",
        aclpubcheck_summary="Already passed",
        aclpubcheck_pdf_sha256=digest,
        checked_at_utc="2026-09-22T12:00:00Z",
    )
    original_csv = csv_path.read_bytes()

    def checker(*args):
        raise AssertionError("unchanged PDF must not be checked")

    summary = check_collection(
        csv_path,
        project_root=tmp_path,
        logs_dir=tmp_path / "logs",
        checker=checker,
    )

    assert summary.checked == 0
    assert summary.skipped == 1
    assert csv_path.read_bytes() == original_csv
    assert read_row(csv_path)["checked_at_utc"] == "2026-09-22T12:00:00Z"


def test_force_rechecks_unchanged_pdf(tmp_path):
    digest = hashlib.sha256(b"%PDF-test-paper").hexdigest()
    csv_path, _ = make_collection(
        tmp_path,
        aclpubcheck_status="pass",
        aclpubcheck_pdf_sha256=digest,
    )
    calls = []

    def checker(pdf, paper_type, executable):
        calls.append(pdf)
        return PubcheckResult("fail", 1, "Margins", "Margins", "aclpubcheck")

    summary = check_collection(
        csv_path,
        project_root=tmp_path,
        logs_dir=tmp_path / "logs",
        force=True,
        checker=checker,
        now=lambda: FIXED_NOW,
    )

    assert summary.checked == 1
    assert summary.failed == 1
    assert len(calls) == 1


def test_rechecks_when_pdf_hash_changed(tmp_path):
    csv_path, _ = make_collection(
        tmp_path,
        aclpubcheck_status="pass",
        aclpubcheck_pdf_sha256="0" * 64,
    )
    calls = []

    def checker(pdf, paper_type, executable):
        calls.append(pdf)
        return PubcheckResult("pass", 0, "Passed", "Passed", "aclpubcheck")

    summary = check_collection(
        csv_path,
        project_root=tmp_path,
        logs_dir=tmp_path / "logs",
        checker=checker,
        now=lambda: FIXED_NOW,
    )

    assert summary.checked == 1
    assert summary.skipped == 0
    assert len(calls) == 1


def test_missing_pdf_is_recorded_as_row_error(tmp_path):
    csv_path, pdf_path = make_collection(tmp_path)
    pdf_path.unlink()

    def checker(*args):
        raise AssertionError("checker must not run for a missing PDF")

    summary = check_collection(
        csv_path,
        project_root=tmp_path,
        logs_dir=tmp_path / "logs",
        checker=checker,
        now=lambda: FIXED_NOW,
    )

    row = read_row(csv_path)
    assert summary.checked == 1
    assert summary.errors == 1
    assert row["aclpubcheck_status"] == "error"
    assert "not found" in row["aclpubcheck_summary"].casefold()
    assert row["aclpubcheck_pdf_sha256"] == ""
    assert row["checked_at_utc"] == "2026-09-23T15:30:00Z"
    assert (tmp_path / "logs/001.log").exists()


def test_invalid_csv_schema_does_not_replace_source(tmp_path):
    csv_path = tmp_path / "papers.csv"
    csv_path.write_text("number,title\n001,Paper\n", encoding="utf-8")
    original_csv = csv_path.read_bytes()

    with pytest.raises(ValueError, match="missing required columns"):
        check_collection(
            csv_path,
            project_root=tmp_path,
            logs_dir=tmp_path / "logs",
        )

    assert csv_path.read_bytes() == original_csv


def test_paper_failure_does_not_stop_later_rows(tmp_path):
    csv_path, _ = make_collection(tmp_path)
    second_pdf = tmp_path / "all_papers/002/paper.pdf"
    second_pdf.parent.mkdir(parents=True)
    second_pdf.write_bytes(b"%PDF-second-paper")
    first = read_row(csv_path)
    second = {
        **first,
        "number": "002",
        "title": "Second Paper",
        "authors": "Bob",
        "openreview_submission_number": "2",
        "paper_type": "short",
        "openreview_url": "https://openreview.net/forum?id=second",
        "pdf_path": "all_papers/002/paper.pdf",
    }
    with csv_path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=first.keys(), lineterminator="\n")
        writer.writerow(second)

    def checker(pdf, paper_type, executable):
        if pdf.name == "paper.pdf" and pdf.parent.name == "001":
            return PubcheckResult("fail", 1, "Bad margins", "Bad margins", "acl")
        return PubcheckResult("pass", 0, "Passed", "Passed", "acl")

    summary = check_collection(
        csv_path,
        project_root=tmp_path,
        logs_dir=tmp_path / "logs",
        checker=checker,
        now=lambda: FIXED_NOW,
    )

    rows = read_rows(csv_path)
    assert [row["aclpubcheck_status"] for row in rows] == ["fail", "pass"]
    assert summary.checked == 2
    assert summary.failed == 1
    assert summary.passed == 1


def test_unknown_paper_type_is_needs_review(tmp_path):
    csv_path, _ = make_collection(tmp_path, paper_type="poster")

    summary = check_collection(
        csv_path,
        project_root=tmp_path,
        logs_dir=tmp_path / "logs",
        now=lambda: FIXED_NOW,
    )

    assert read_row(csv_path)["aclpubcheck_status"] == "needs_review"
    assert summary.needs_review == 1

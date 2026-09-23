import csv

from groundlm_collector.report import CSV_COLUMNS, PaperRow, write_csv


def paper_row(**overrides):
    values = {
        "number": "001",
        "title": "Grounding, Faithfully",
        "authors": ("王一木", "Doe, Jane"),
        "source_venue": "GroundLM",
        "track": "Track 1: Direct Submission",
        "openreview_submission_number": 3,
        "decision": "Accept",
        "archival_status": "archival",
        "paper_type": "long",
        "aclpubcheck_status": "pending",
        "aclpubcheck_summary": "Not run",
        "aclpubcheck_pdf_sha256": "",
        "openreview_url": "https://openreview.net/forum?id=forum-1",
        "pdf_path": "all_papers/001/paper.pdf",
        "supplementary_files": (
            "all_papers/001/supplementary/Supplementary_material.zip",
        ),
        "checked_at_utc": "",
    }
    values.update(overrides)
    return PaperRow(**values)


def test_csv_round_trip_preserves_unicode_commas_and_multiple_authors(tmp_path):
    path = tmp_path / "papers.csv"

    write_csv(path, [paper_row()])

    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        row = next(reader)
        assert reader.fieldnames == list(CSV_COLUMNS)
    assert row["title"] == "Grounding, Faithfully"
    assert row["authors"] == "王一木; Doe, Jane"
    assert row["supplementary_files"].endswith("Supplementary_material.zip")
    assert row["aclpubcheck_pdf_sha256"] == ""
    assert "aclpubcheck_pdf_sha256" in CSV_COLUMNS


def test_csv_uses_lf_and_atomic_write(tmp_path):
    path = tmp_path / "papers.csv"

    write_csv(path, [paper_row(title="One\nLine")])

    data = path.read_bytes()
    assert b"\r\n" not in data
    assert list(tmp_path.glob("*.tmp")) == []

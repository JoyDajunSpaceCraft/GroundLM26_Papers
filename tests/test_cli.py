import csv
from types import SimpleNamespace

from groundlm_collector.cli import download_collection


def fake_client():
    client = SimpleNamespace()
    client.get_group = lambda venue_id: SimpleNamespace(
        content={
            "submission_id": {"value": f"{venue_id}/-/Submission"},
            "decision_heading_map": {"value": {venue_id: "Accept"}},
        }
    )
    submission = SimpleNamespace(
        id="note-1",
        forum="forum-1",
        number=4,
        content={
            "title": {"value": "A Paper"},
            "authors": {"value": ["Alice"]},
            "authorids": {"value": ["~Alice1"]},
            "submission_type": {"value": "Archival Long Paper"},
            "submission_track": {"value": "Track 1"},
            "venue": {"value": "Venue"},
            "pdf": {"value": "/pdf/hash.pdf"},
            "Supplementary_material": {"value": "/attachment/hash.zip"},
        },
    )
    client.get_all_notes = lambda **kwargs: [submission]
    client.get_attachment = lambda field_name, id: (
        b"%PDF-test" if field_name == "pdf" else b"PK-test"
    )
    return client


def test_download_collection_creates_numbered_files_manifest_and_csv(tmp_path):
    summary = download_collection(
        fake_client(), project_root=tmp_path, venue_ids=("Venue",)
    )

    assert summary.included == 1
    assert summary.downloaded == 1
    assert (tmp_path / "all_papers/001/paper.pdf").exists()
    assert (tmp_path / "all_papers/manifest.json").exists()
    with (tmp_path / "papers.csv").open(encoding="utf-8", newline="") as handle:
        row = next(csv.DictReader(handle))
    assert row["number"] == "001"
    assert row["aclpubcheck_status"] == "pending"
    assert row["aclpubcheck_pdf_sha256"] == ""


def test_download_collection_dry_run_writes_nothing(tmp_path):
    summary = download_collection(
        fake_client(), project_root=tmp_path, venue_ids=("Venue",), dry_run=True
    )

    assert summary.included == 1
    assert summary.downloaded == 0
    assert not (tmp_path / "all_papers").exists()
    assert not (tmp_path / "papers.csv").exists()

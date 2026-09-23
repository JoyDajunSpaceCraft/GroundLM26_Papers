import csv
from types import SimpleNamespace

import groundlm_collector.cli as cli
from groundlm_collector.cli import _parse_args, download_collection


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


def test_parse_check_command_options():
    args = _parse_args(
        [
            "check",
            "--force",
            "--csv",
            "custom.csv",
            "--logs-dir",
            "check-logs",
        ]
    )

    assert args.command == "check"
    assert args.force is True
    assert args.csv.name == "custom.csv"
    assert args.logs_dir.name == "check-logs"


def test_check_command_does_not_load_openreview_credentials(
    tmp_path, monkeypatch, capsys
):
    calls = []

    def fail_if_credentials_are_loaded():
        raise AssertionError("check must not load OpenReview credentials")

    def fake_check_collection(csv_path, project_root, logs_dir, *, force):
        calls.append((csv_path, project_root, logs_dir, force))
        return SimpleNamespace(
            total=90,
            checked=2,
            skipped=88,
            passed=1,
            failed=1,
            errors=0,
            needs_review=0,
        )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "load_keychain_credential", fail_if_credentials_are_loaded)
    monkeypatch.setattr(cli, "check_collection", fake_check_collection)

    exit_code = cli.main(["check", "--force"])

    assert exit_code == 0
    assert calls == [
        (tmp_path / "papers.csv", tmp_path, tmp_path / "aclpubcheck-logs", True)
    ]
    output = capsys.readouterr().out
    assert "checked=2" in output
    assert "failed=1" in output

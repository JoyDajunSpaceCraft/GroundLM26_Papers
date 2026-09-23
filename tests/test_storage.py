from pathlib import Path

import pytest

from groundlm_collector.models import ClassifiedSubmission, RawSubmission
from groundlm_collector.storage import (
    Manifest,
    atomic_write_bytes,
    load_manifest,
    materialize_paper,
    retire_absent_assignments,
    safe_filename,
    save_manifest,
)


@pytest.mark.parametrize("unsafe", ["../../secret", "/tmp/x", "..\\..\\x", ""])
def test_safe_filename_stays_inside_attachment_directory(unsafe):
    name = safe_filename(unsafe, "supplementary.bin")
    assert name not in {"", ".", ".."}
    assert Path(name).name == name
    assert "/" not in name
    assert "\\" not in name


def test_atomic_write_replaces_complete_file(tmp_path):
    target = tmp_path / "paper.pdf"
    target.write_bytes(b"old")

    atomic_write_bytes(target, b"%PDF-new")

    assert target.read_bytes() == b"%PDF-new"
    assert list(tmp_path.glob("*.tmp")) == []


def test_manifest_round_trip_preserves_retired_numbers(tmp_path):
    manifest = Manifest(
        assignments={"forum-a": "001"},
        retired={"forum-old": "002"},
        files={"forum-a": {"pdf": {"sha256": "abc"}}},
    )

    save_manifest(tmp_path / "manifest.json", manifest)

    assert load_manifest(tmp_path / "manifest.json") == manifest


def test_retire_absent_assignments_does_not_recycle_number():
    manifest = Manifest(
        assignments={"keep": "001", "gone": "002"},
        retired={},
        files={},
    )

    updated = retire_absent_assignments(manifest, active_forums={"keep"})

    assert updated.assignments == {"keep": "001"}
    assert updated.retired == {"gone": "002"}


def test_materialize_paper_writes_pdf_and_supplement_with_field_name(tmp_path):
    raw = RawSubmission(
        note_id="note-1",
        forum="forum-1",
        number=4,
        source_venue="Venue",
        title="Paper",
        authors=("Alice",),
        author_ids=(),
        decision="Accept",
        venue_value="Venue",
        submission_type="Archival Long Paper",
        track="Track",
        attachments={
            "pdf": "/pdf/hash.pdf",
            "Supplementary_material": "/attachment/hash.zip",
        },
    )
    record = ClassifiedSubmission(
        raw=raw,
        selection_status="included",
        archival_status="archival",
        paper_type="long",
        track="Track",
        reason="test",
    )
    payloads = {
        "pdf": b"%PDF-test",
        "Supplementary_material": b"PK-test",
    }

    result = materialize_paper(
        tmp_path / "all_papers",
        "001",
        record,
        lambda note_id, field: payloads[field],
    )

    assert (tmp_path / "all_papers/001/paper.pdf").read_bytes() == b"%PDF-test"
    supplement = tmp_path / "all_papers/001/supplementary/Supplementary_material.zip"
    assert supplement.read_bytes() == b"PK-test"
    assert result.pdf_path == "all_papers/001/paper.pdf"
    assert result.supplementary_paths == (
        "all_papers/001/supplementary/Supplementary_material.zip",
    )

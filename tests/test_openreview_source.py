from types import SimpleNamespace
from unittest.mock import Mock

from groundlm_collector.openreview_source import (
    attachment_fields,
    discover_venue,
    download_attachment,
    fetch_submissions,
    unwrap,
)


def note(*, note_id="note-1", forum="forum-1", number=3, content=None):
    return SimpleNamespace(
        id=note_id,
        forum=forum,
        number=number,
        content=content or {},
    )


def test_unwrap_v2_content_value():
    assert unwrap({"value": ["Alice", "Bob"]}) == ["Alice", "Bob"]
    assert unwrap("already plain") == "already plain"


def test_attachment_fields_puts_pdf_first_and_finds_supplement():
    submission = note(
        content={
            "pdf": {"value": "/pdf/hash.pdf"},
            "Supplementary_material": {"value": "/attachment/hash.zip"},
            # OpenReview may expose this confidential export to chairs. It must
            # be ignored even though its value looks like an attachment.
            "reviews_and_meta_reviews": {"value": "/attachment/reviews.pdf"},
            "title": {"value": "Paper"},
        }
    )

    assert attachment_fields(submission) == ["pdf", "Supplementary_material"]


def test_discover_venue_uses_group_decision_map_and_observed_fields():
    client = Mock()
    client.get_group.return_value = SimpleNamespace(
        content={
            "submission_id": {"value": "Venue/-/Submission"},
            "decision_heading_map": {
                "value": {
                    "Venue": "Accept",
                    "Venue Findings": "Findings",
                    "Submitted to Venue": "Reject",
                }
            },
        }
    )
    client.get_all_notes.return_value = [
        note(
            content={
                "title": {"value": "Paper"},
                "submission_type": {"value": "Archival Long Paper"},
                "submission_track": {"value": "Track 1"},
                "pdf": {"value": "/pdf/hash.pdf"},
            }
        )
    ]

    schema = discover_venue(client, "Venue")

    assert schema.submission_invitation == "Venue/-/Submission"
    assert schema.decision_by_venue == {
        "Venue": "Accept",
        "Venue Findings": "Findings",
        "Submitted to Venue": "Reject",
    }
    assert schema.submission_type_field == "submission_type"
    assert schema.track_field == "submission_track"
    assert schema.attachment_fields == ("pdf",)


def test_fetch_uses_get_all_notes_and_normalizes_records():
    client = Mock()
    client.get_all_notes.return_value = [
        note(
            content={
                "title": {"value": "Paper"},
                "authors": {"value": ["Alice", "Bob"]},
                "submission_type": {"value": "Archival Short Paper"},
                "submission_track": {"value": "Track 1"},
                "venue": {"value": "Venue"},
                "pdf": {"value": "/pdf/hash.pdf"},
            }
        )
    ]
    schema = SimpleNamespace(
        venue_id="Venue",
        submission_invitation="Venue/-/Submission",
        decision_by_venue={"Venue": "Accept"},
        submission_type_field="submission_type",
        track_field="submission_track",
        attachment_fields=("pdf",),
    )

    records = fetch_submissions(client, schema)

    client.get_all_notes.assert_called_once_with(invitation="Venue/-/Submission")
    assert len(records) == 1
    assert records[0].title == "Paper"
    assert records[0].authors == ("Alice", "Bob")
    assert records[0].decision == "Accept"
    assert records[0].submission_type == "Archival Short Paper"
    assert records[0].attachments == {"pdf": "/pdf/hash.pdf"}


def test_download_attachment_delegates_to_api_v2_client():
    client = Mock()
    client.get_attachment.return_value = b"%PDF-test"

    result = download_attachment(client, "note-1", "pdf")

    assert result == b"%PDF-test"
    client.get_attachment.assert_called_once_with(field_name="pdf", id="note-1")

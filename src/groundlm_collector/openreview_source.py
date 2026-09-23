"""Read-only access to GroundLM submissions in OpenReview API v2."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .models import RawSubmission, VenueSchema


# OpenReview exposes this organizer-only export as an attachment, but it is not
# supplementary material and must never be included in proceedings artifacts.
NON_PROCEEDINGS_ATTACHMENT_FIELDS = {"reviews_and_meta_reviews"}


def unwrap(value: object) -> object:
    if isinstance(value, Mapping) and "value" in value:
        return value["value"]
    return value


def _content_value(note: Any, field_name: str, default: object = None) -> object:
    return unwrap(note.content.get(field_name, default))


def attachment_fields(note: Any) -> list[str]:
    fields: list[str] = []
    for field_name, raw_value in note.content.items():
        if field_name.casefold() in NON_PROCEEDINGS_ATTACHMENT_FIELDS:
            continue
        value = unwrap(raw_value)
        if isinstance(value, str) and value.startswith(("/pdf/", "/attachment/")):
            fields.append(field_name)
    return sorted(fields, key=lambda name: (name.lower() != "pdf", name.casefold()))


def discover_venue(client: Any, venue_id: str) -> VenueSchema:
    group = client.get_group(venue_id)
    submission_invitation = str(unwrap(group.content["submission_id"]))
    decision_by_venue = dict(
        unwrap(group.content.get("decision_heading_map", {"value": {}})) or {}
    )
    notes = client.get_all_notes(invitation=submission_invitation)
    observed_fields = {field for note in notes for field in note.content}

    all_attachment_fields = {
        field for note in notes for field in attachment_fields(note)
    }
    ordered_attachments = tuple(
        sorted(
            all_attachment_fields,
            key=lambda name: (name.lower() != "pdf", name.casefold()),
        )
    )

    return VenueSchema(
        venue_id=venue_id,
        submission_invitation=submission_invitation,
        decision_by_venue=decision_by_venue,
        submission_type_field=(
            "submission_type" if "submission_type" in observed_fields else None
        ),
        track_field="submission_track" if "submission_track" in observed_fields else None,
        attachment_fields=ordered_attachments,
    )


def fetch_submissions(client: Any, schema: VenueSchema) -> list[RawSubmission]:
    notes = client.get_all_notes(invitation=schema.submission_invitation)
    records: list[RawSubmission] = []
    for note in notes:
        venue_value = _optional_string(_content_value(note, "venue"))
        attachments = {
            field_name: value
            for field_name in schema.attachment_fields
            if isinstance((value := _content_value(note, field_name)), str)
            and value.startswith(("/pdf/", "/attachment/"))
        }
        records.append(
            RawSubmission(
                note_id=str(note.id),
                forum=str(note.forum or note.id),
                number=int(note.number),
                source_venue=schema.venue_id,
                title=str(_content_value(note, "title", "")),
                authors=_string_tuple(_content_value(note, "authors", [])),
                author_ids=_string_tuple(_content_value(note, "authorids", [])),
                decision=schema.decision_by_venue.get(venue_value or ""),
                venue_value=venue_value,
                submission_type=(
                    _optional_string(
                        _content_value(note, schema.submission_type_field)
                    )
                    if schema.submission_type_field
                    else None
                ),
                track=(
                    _optional_string(_content_value(note, schema.track_field))
                    if schema.track_field
                    else None
                ),
                attachments=attachments,
            )
        )
    return records


def download_attachment(client: Any, note_id: str, field_name: str) -> bytes:
    data = client.get_attachment(field_name=field_name, id=note_id)
    if not isinstance(data, bytes):
        raise TypeError(
            f"OpenReview returned {type(data).__name__} for attachment {field_name!r}; "
            "expected bytes."
        )
    return data


def _string_tuple(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, (list, tuple)):
        return tuple(str(item) for item in value)
    return (str(value),)


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None

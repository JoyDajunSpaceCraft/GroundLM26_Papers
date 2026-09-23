"""Shared data models for the GroundLM collector."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True, slots=True)
class VenueSchema:
    venue_id: str
    submission_invitation: str
    decision_by_venue: dict[str, str]
    submission_type_field: str | None
    track_field: str | None
    attachment_fields: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RawSubmission:
    note_id: str
    forum: str
    number: int
    source_venue: str
    title: str
    authors: tuple[str, ...]
    author_ids: tuple[str, ...]
    decision: str | None
    venue_value: str | None
    submission_type: str | None
    track: str | None
    attachments: dict[str, str] = field(default_factory=dict)


SelectionStatus = Literal["included", "excluded", "needs_review"]


@dataclass(frozen=True, slots=True)
class ClassifiedSubmission:
    raw: RawSubmission
    selection_status: SelectionStatus
    archival_status: str
    paper_type: Literal["long", "short"] | None
    track: str
    reason: str


@dataclass(frozen=True, slots=True)
class SelectionResult:
    included: tuple[ClassifiedSubmission, ...]
    excluded: tuple[ClassifiedSubmission, ...]
    needs_review: tuple[ClassifiedSubmission, ...]

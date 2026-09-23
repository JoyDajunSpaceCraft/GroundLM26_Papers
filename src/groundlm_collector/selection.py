"""Pure selection, duplicate detection, and stable numbering rules."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
import re
import unicodedata

from .models import ClassifiedSubmission, RawSubmission, SelectionResult


DIRECT_VENUE = "EMNLP/2026/Workshop/GroundLM"
ARR_VENUE = "EMNLP/2026/Workshop/GroundLM_ARR_Commitment"
SHARED_TASK_VENUE = "EMNLP/2026/Workshop/GroundLM_Shared_Tasks"

VENUE_RANK = {
    DIRECT_VENUE: 0,
    ARR_VENUE: 1,
    SHARED_TASK_VENUE: 2,
}

TRACK_FALLBACK = {
    DIRECT_VENUE: "Track 1: Direct Submission",
    ARR_VENUE: "Track 2: ARR Commitment",
    SHARED_TASK_VENUE: "Shared Tasks",
}


def classify(raw: RawSubmission) -> ClassifiedSubmission:
    track = raw.track or TRACK_FALLBACK.get(raw.source_venue, raw.source_venue)
    decision = (raw.decision or "").strip().casefold()
    if decision not in {"accept", "findings"}:
        return ClassifiedSubmission(
            raw=raw,
            selection_status="excluded",
            archival_status="unknown",
            paper_type=None,
            track=track,
            reason=f"final decision is {raw.decision or 'missing'}",
        )

    if raw.source_venue == SHARED_TASK_VENUE:
        return ClassifiedSubmission(
            raw=raw,
            selection_status="included",
            archival_status="archival",
            paper_type="long",
            track="Shared Tasks",
            reason="accepted Shared Tasks paper; organizer specified archival long",
        )

    submission_type = (raw.submission_type or "").strip()
    normalized_type = submission_type.casefold()
    if normalized_type.startswith("non-archival"):
        return ClassifiedSubmission(
            raw=raw,
            selection_status="excluded",
            archival_status="non-archival",
            paper_type=None,
            track=track,
            reason=f"submission type is {submission_type}",
        )
    if normalized_type.startswith("archival long"):
        return ClassifiedSubmission(
            raw=raw,
            selection_status="included",
            archival_status="archival",
            paper_type="long",
            track=track,
            reason=f"{raw.decision} archival long paper",
        )
    if normalized_type.startswith("archival short"):
        return ClassifiedSubmission(
            raw=raw,
            selection_status="included",
            archival_status="archival",
            paper_type="short",
            track=track,
            reason=f"{raw.decision} archival short paper",
        )
    return ClassifiedSubmission(
        raw=raw,
        selection_status="needs_review",
        archival_status="unknown",
        paper_type=None,
        track=track,
        reason=f"unrecognized submission type: {submission_type or 'missing'}",
    )


def select_archival(records: Iterable[RawSubmission]) -> SelectionResult:
    classified = [classify(record) for record in records]
    return SelectionResult(
        included=tuple(
            item for item in classified if item.selection_status == "included"
        ),
        excluded=tuple(
            item for item in classified if item.selection_status == "excluded"
        ),
        needs_review=tuple(
            item for item in classified if item.selection_status == "needs_review"
        ),
    )


def find_duplicate_candidates(
    records: Iterable[RawSubmission],
) -> list[list[RawSubmission]]:
    grouped: dict[tuple[str, tuple[str, ...]], list[RawSubmission]] = defaultdict(list)
    for record in records:
        key = (
            _normalize_text(record.title),
            tuple(_normalize_text(author) for author in record.authors),
        )
        grouped[key].append(record)
    duplicates = [group for group in grouped.values() if len(group) > 1]
    return sorted(
        duplicates,
        key=lambda group: min(
            (VENUE_RANK.get(item.source_venue, 99), item.number) for item in group
        ),
    )


def assign_numbers(
    records: Iterable[RawSubmission], existing: Mapping[str, str]
) -> dict[str, str]:
    result = dict(existing)
    used = {int(value) for value in existing.values() if str(value).isdigit()}
    next_number = max(used, default=0) + 1
    new_records = sorted(
        (record for record in records if record.forum not in result),
        key=lambda record: (
            VENUE_RANK.get(record.source_venue, 99),
            record.number,
            record.forum,
        ),
    )
    for record in new_records:
        while next_number in used:
            next_number += 1
        result[record.forum] = f"{next_number:03d}"
        used.add(next_number)
        next_number += 1
    return result


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return re.sub(r"\s+", " ", normalized).strip()

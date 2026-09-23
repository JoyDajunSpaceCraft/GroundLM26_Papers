from groundlm_collector.models import RawSubmission
from groundlm_collector.selection import (
    assign_numbers,
    classify,
    find_duplicate_candidates,
    select_archival,
)


DIRECT = "EMNLP/2026/Workshop/GroundLM"
ARR = "EMNLP/2026/Workshop/GroundLM_ARR_Commitment"
SHARED = "EMNLP/2026/Workshop/GroundLM_Shared_Tasks"


def record(
    *,
    forum="forum-1",
    number=1,
    source_venue=DIRECT,
    title="Paper",
    authors=("Alice",),
    decision="Accept",
    submission_type="Archival Long Paper (8 pages limitation for the main body)",
):
    return RawSubmission(
        note_id=f"note-{forum}",
        forum=forum,
        number=number,
        source_venue=source_venue,
        title=title,
        authors=tuple(authors),
        author_ids=(),
        decision=decision,
        venue_value=None,
        submission_type=submission_type,
        track=None,
        attachments={"pdf": "/pdf/test.pdf"},
    )


def test_accept_archival_long_is_included():
    result = classify(record())
    assert result.selection_status == "included"
    assert result.archival_status == "archival"
    assert result.paper_type == "long"


def test_findings_archival_short_is_included():
    result = classify(
        record(
            decision="Findings",
            submission_type="Archival Short Paper (4 pages limitation for the main body)",
        )
    )
    assert result.selection_status == "included"
    assert result.paper_type == "short"


def test_accept_non_archival_is_excluded():
    result = classify(
        record(
            submission_type="Non-Archival Paper (8 pages limitation for the main body)"
        )
    )
    assert result.selection_status == "excluded"
    assert result.archival_status == "non-archival"


def test_reject_is_excluded_even_if_archival():
    result = classify(record(decision="Reject"))
    assert result.selection_status == "excluded"


def test_missing_type_on_regular_track_needs_review():
    result = classify(record(submission_type=None))
    assert result.selection_status == "needs_review"


def test_shared_task_accept_is_archival_long_by_organizer_rule():
    result = classify(
        record(source_venue=SHARED, submission_type=None, title="System paper")
    )
    assert result.selection_status == "included"
    assert result.archival_status == "archival"
    assert result.paper_type == "long"
    assert result.track == "Shared Tasks"


def test_select_archival_partitions_records():
    result = select_archival(
        [
            record(forum="included"),
            record(forum="excluded", submission_type="Non-Archival Paper"),
            record(forum="review", submission_type=None),
        ]
    )
    assert [item.raw.forum for item in result.included] == ["included"]
    assert [item.raw.forum for item in result.excluded] == ["excluded"]
    assert [item.raw.forum for item in result.needs_review] == ["review"]


def test_existing_forum_keeps_number_and_new_forum_gets_next_unused():
    result = assign_numbers(
        [record(forum="old", number=7), record(forum="new", number=1)],
        {"old": "007"},
    )
    assert result == {"old": "007", "new": "008"}


def test_new_numbering_uses_venue_rank_then_submission_number():
    result = assign_numbers(
        [
            record(forum="shared", source_venue=SHARED, number=1),
            record(forum="arr", source_venue=ARR, number=1),
            record(forum="direct", source_venue=DIRECT, number=3),
        ],
        {},
    )
    assert result == {"direct": "001", "arr": "002", "shared": "003"}


def test_duplicate_candidates_normalize_title_and_authors():
    duplicates = find_duplicate_candidates(
        [
            record(
                forum="a",
                title="A  Grounded Model",
                authors=("A. Li", "B. Doe"),
            ),
            record(
                forum="b",
                title="a grounded model",
                authors=("a. li", "b. doe"),
            ),
        ]
    )
    assert [[item.forum for item in group] for group in duplicates] == [["a", "b"]]

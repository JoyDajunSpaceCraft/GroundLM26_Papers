from groundlm_collector.models import RawSubmission
from groundlm_collector.notifications import (
    NotificationPaper,
    group_papers_by_author,
    matches_mode,
    render_message,
)


def raw(
    *,
    forum="forum-1",
    venue="EMNLP/2026/Workshop/GroundLM",
    decision="Accept",
    submission_type="Archival Long Paper",
    author_ids=("~Alice", "~Bob"),
):
    return RawSubmission(
        note_id=forum,
        forum=forum,
        number=1,
        source_venue=venue,
        title="A Paper",
        authors=("Alice", "Bob"),
        author_ids=author_ids,
        decision=decision,
        venue_value=decision,
        submission_type=submission_type,
        track=None,
        attachments={},
    )


def test_archival_and_non_archival_modes_require_accept_or_findings():
    assert matches_mode(raw(), "archival") is True
    assert matches_mode(raw(decision="Findings"), "archival") is True
    assert matches_mode(raw(decision="Reject"), "archival") is False
    assert (
        matches_mode(
            raw(submission_type="Non-Archival Long Paper"), "non-archival"
        )
        is True
    )
    assert (
        matches_mode(
            raw(submission_type="Non-Archival Long Paper", decision="Findings"),
            "non-archival",
        )
        is True
    )
    assert (
        matches_mode(raw(submission_type="Non-Archival Long Paper"), "archival")
        is False
    )


def test_shared_tasks_are_archival_and_non_archival_is_not_shared_task():
    shared = raw(
        venue="EMNLP/2026/Workshop/GroundLM_Shared_Tasks",
        submission_type=None,
    )

    assert matches_mode(shared, "archival") is True
    assert matches_mode(shared, "non-archival") is False


def test_group_papers_by_author_deduplicates_case_insensitively():
    papers = [
        NotificationPaper("001", "forum-1", "First", ("~Alice", "~Bob")),
        NotificationPaper("002", "forum-2", "Second", ("~alice",)),
    ]

    grouped = group_papers_by_author(papers)

    assert list(grouped) == ["~Alice", "~Bob"]
    assert [paper.number for paper in grouped["~Alice"]] == ["001", "002"]
    assert [paper.number for paper in grouped["~Bob"]] == ["001"]


def test_render_message_lists_papers_and_private_repo_request():
    message = render_message(
        [
            NotificationPaper("001", "forum-1", "First Paper", ("~Alice",)),
            NotificationPaper("002", "forum-2", "Second Paper", ("~Alice",)),
        ],
        repo_url="https://github.com/groundlm/GroundLM26_Papers",
    )

    assert "001 — First Paper" in message
    assert "002 — Second Paper" in message
    assert "https://github.com/groundlm/GroundLM26_Papers" in message
    assert "paper PDF" in message
    assert "supplementary" in message

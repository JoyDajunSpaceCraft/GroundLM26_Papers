import csv
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from groundlm_collector.models import RawSubmission
from groundlm_collector.notifier import (
    build_target_papers,
    send_notifications,
)


def raw(
    *,
    forum,
    venue="EMNLP/2026/Workshop/GroundLM",
    number=1,
    decision="Accept",
    submission_type="Archival Long Paper",
    author_ids=("~Alice",),
):
    return RawSubmission(
        note_id=forum,
        forum=forum,
        number=number,
        source_venue=venue,
        title=f"Title {forum}",
        authors=("Alice",),
        author_ids=author_ids,
        decision=decision,
        venue_value=decision,
        submission_type=submission_type,
        track=None,
        attachments={},
    )


def test_paper_mode_selects_requested_csv_number():
    records = [raw(forum="forum-1"), raw(forum="forum-2", number=2)]
    rows = [
        {
            "number": "007",
            "openreview_url": "https://openreview.net/forum?id=forum-2",
        }
    ]

    result = build_target_papers(records, "paper", csv_rows=rows, paper_number="007")

    assert [paper.number for paper in result] == ["007"]
    assert result[0].forum == "forum-2"


def test_archival_mode_matches_current_csv_paper_list():
    records = [
        raw(forum="forum-1"),
        raw(forum="forum-2", decision="Findings", number=2),
        raw(
            forum="forum-3",
            decision="Accept",
            submission_type="Non-Archival Long Paper",
            number=3,
        ),
    ]
    rows = [
        {"number": "001", "openreview_url": "https://openreview.net/forum?id=forum-1"},
        {"number": "002", "openreview_url": "https://openreview.net/forum?id=forum-2"},
    ]

    result = build_target_papers(records, "archival", csv_rows=rows)

    assert [paper.number for paper in result] == ["001", "002"]


def test_non_archival_mode_selects_only_accept_and_findings():
    records = [
        raw(
            forum="forum-1",
            submission_type="Non-Archival Long Paper",
            decision="Accept",
        ),
        raw(
            forum="forum-2",
            submission_type="Non-Archival Short Paper",
            decision="Findings",
        ),
        raw(
            forum="forum-3",
            submission_type="Non-Archival Long Paper",
            decision="Reject",
        ),
    ]

    result = build_target_papers(records, "non-archival")

    assert [paper.forum for paper in result] == ["forum-1", "forum-2"]


def test_send_notifications_uses_openreview_direct_message_api(tmp_path):
    client = Mock()
    plan = build_target_papers(
        [raw(forum="forum-1", author_ids=("~Alice", "~Bob"))],
        "archival",
        csv_rows=[
            {"number": "001", "openreview_url": "https://openreview.net/forum?id=forum-1"}
        ],
    )

    result = send_notifications(
        client,
        plan,
        subject="Please check GroundLM materials",
        repo_url="https://github.com/groundlm/GroundLM26_Papers",
        send=True,
        yes=True,
        log_path=tmp_path / "messages.jsonl",
    )

    assert result.sent == 2
    assert client.post_direct_message.call_count == 2
    recipients = {
        call.args[1][0] for call in client.post_direct_message.call_args_list
    }
    assert recipients == {"~Alice", "~Bob"}
    assert (tmp_path / "messages.jsonl").read_text(encoding="utf-8").count("\n") == 2


def test_send_requires_explicit_confirmation():
    with pytest.raises(ValueError, match="--yes"):
        send_notifications(
            Mock(),
            [],
            subject="Subject",
            repo_url="https://example.com",
            send=True,
            yes=False,
        )

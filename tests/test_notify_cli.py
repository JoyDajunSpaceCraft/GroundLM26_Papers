from types import SimpleNamespace

import groundlm_collector.notify_cli as notify_cli
from groundlm_collector.models import RawSubmission


def test_parse_requires_one_target_mode():
    args = notify_cli._parse_args(["--paper", "003"])

    assert args.paper == "003"
    assert args.archival is False
    assert args.non_archival is False
    assert args.send is False


def test_dry_run_does_not_send_messages(tmp_path, monkeypatch, capsys):
    record = RawSubmission(
        note_id="forum-1",
        forum="forum-1",
        number=1,
        source_venue="EMNLP/2026/Workshop/GroundLM",
        title="A Paper",
        authors=("Alice",),
        author_ids=("~Alice",),
        decision="Accept",
        venue_value="Accept",
        submission_type="Archival Long Paper",
        track=None,
        attachments={},
    )
    client = SimpleNamespace(post_direct_message=lambda *args, **kwargs: None)
    monkeypatch.setattr(notify_cli, "create_client", lambda credential: client)
    monkeypatch.setattr(notify_cli, "load_keychain_credential", lambda: object())
    monkeypatch.setattr(notify_cli, "discover_records", lambda client: [record])
    monkeypatch.chdir(tmp_path)
    (tmp_path / "papers.csv").write_text(
        "number,openreview_url\n001,https://openreview.net/forum?id=forum-1\n",
        encoding="utf-8",
    )

    assert notify_cli.main(["--paper", "001"]) == 0
    output = capsys.readouterr().out
    assert "~Alice" in output
    assert "dry-run" in output

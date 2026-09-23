from pathlib import Path


WORKFLOW = Path(".github/workflows/aclpubcheck.yml")
ACLPUBCHECK_REVISION = "237bee3a554f2d2fcda69cd0cf1edf4168e3d339"


def test_aclpubcheck_workflow_contract():
    assert WORKFLOW.is_file()
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "workflow_dispatch:" in text
    assert "type: boolean" in text
    assert "all_papers/*/paper.pdf" in text
    assert "contents: write" in text
    assert (
        "git+https://github.com/acl-org/aclpubcheck.git@"
        + ACLPUBCHECK_REVISION
    ) in text
    assert "groundlm-collect check" in text
    assert "if: always()" in text
    assert "actions/upload-artifact@v4" in text
    assert "git add -- papers.csv" in text
    assert "git add ." not in text
    assert "git add -A" not in text


def test_csv_only_bot_commit_cannot_retrigger_workflow():
    text = WORKFLOW.read_text(encoding="utf-8")
    push_section = text.split("push:", 1)[1].split("permissions:", 1)[0]

    assert "papers.csv" not in push_section

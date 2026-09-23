from subprocess import CompletedProcess

import pytest

from groundlm_collector.pubcheck import (
    UnknownPaperType,
    paper_type_arg,
    run_pubcheck,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Long Paper", "long"),
        ("long", "long"),
        ("Archival Long Paper (8 pages)", "long"),
        ("Short Paper", "short"),
        ("short", "short"),
        ("Archival Short Paper (4 pages)", "short"),
    ],
)
def test_paper_type_arg(value, expected):
    assert paper_type_arg(value) == expected


def test_unknown_paper_type_needs_review():
    with pytest.raises(UnknownPaperType):
        paper_type_arg("System Demonstration")


def test_zero_checker_exit_is_pass(tmp_path):
    def runner(args, **kwargs):
        return CompletedProcess(args, 0, "Checking paper.pdf\nAll Clear!\n", "")

    result = run_pubcheck(
        tmp_path / "paper.pdf", "long", ["aclpubcheck"], runner=runner
    )

    assert result.status == "pass"
    assert result.exit_code == 0
    assert result.summary == "All Clear!"


def test_zero_exit_with_reported_errors_is_fail(tmp_path):
    def runner(args, **kwargs):
        return CompletedProcess(
            args,
            0,
            "Checking paper.pdf\n"
            "Error (Margin): Text on page 2 bleeds into the right margin.\n"
            "We detected 1 error and 0 warnings in your paper.\n",
            "",
        )

    result = run_pubcheck(
        tmp_path / "paper.pdf", "long", ["aclpubcheck"], runner=runner
    )

    assert result.status == "fail"
    assert "We detected 1 error" in result.summary
    assert "Margin" in result.summary


def test_zero_exit_with_warnings_only_is_pass(tmp_path):
    def runner(args, **kwargs):
        return CompletedProcess(
            args,
            0,
            "Checking paper.pdf\n"
            "Warning (Bibliography): Check a citation.\n"
            "We detected 0 errors and 1 warning in your paper.\n",
            "",
        )

    result = run_pubcheck(
        tmp_path / "paper.pdf", "short", ["aclpubcheck"], runner=runner
    )

    assert result.status == "pass"
    assert "0 errors" in result.summary


def test_parsing_error_is_checker_error(tmp_path):
    def runner(args, **kwargs):
        return CompletedProcess(
            args,
            0,
            "Checking paper.pdf\nParsing Error: Error occurs when parsing page [3].\n"
            "We detected 0 errors and 0 warnings in your paper.\n",
            "",
        )

    result = run_pubcheck(
        tmp_path / "paper.pdf", "long", ["aclpubcheck"], runner=runner
    )

    assert result.status == "error"
    assert "Parsing Error" in result.summary


def test_nonzero_checker_exit_is_error(tmp_path):
    def runner(args, **kwargs):
        return CompletedProcess(args, 1, "Margin violation on page 2\n", "")

    result = run_pubcheck(
        tmp_path / "paper.pdf", "long", ["aclpubcheck"], runner=runner
    )

    assert result.status == "error"
    assert result.exit_code == 1
    assert "Margin violation" in result.summary


def test_checker_launch_failure_is_error(tmp_path):
    def runner(args, **kwargs):
        raise FileNotFoundError("aclpubcheck")

    result = run_pubcheck(
        tmp_path / "paper.pdf", "short", ["aclpubcheck"], runner=runner
    )

    assert result.status == "error"
    assert result.exit_code is None
    assert "not found" in result.summary.casefold()

"""ACL pubcheck invocation and deterministic result classification."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
import subprocess
import re
from typing import Literal


class UnknownPaperType(ValueError):
    """Raised when a paper cannot be mapped to ACL long or short type."""


@dataclass(frozen=True, slots=True)
class PubcheckResult:
    status: Literal["pass", "fail", "error", "needs_review"]
    exit_code: int | None
    summary: str
    output: str
    command_version: str


def paper_type_arg(value: str) -> Literal["long", "short"]:
    normalized = value.strip().casefold()
    if normalized == "long" or "long paper" in normalized:
        return "long"
    if normalized == "short" or "short paper" in normalized:
        return "short"
    raise UnknownPaperType(f"Unknown ACL paper type: {value!r}")


def run_pubcheck(
    pdf: Path,
    paper_type: str,
    executable: Sequence[str] = ("aclpubcheck",),
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> PubcheckResult:
    try:
        acl_type = paper_type_arg(paper_type)
    except UnknownPaperType as error:
        return PubcheckResult(
            status="needs_review",
            exit_code=None,
            summary=str(error),
            output=str(error),
            command_version=" ".join(executable),
        )

    command = [*executable, "--paper_type", acl_type, str(pdf)]
    try:
        completed = runner(
            command,
            check=False,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.SubprocessError) as error:
        detail = (
            f"executable not found: {error}"
            if isinstance(error, FileNotFoundError)
            else str(error)
        )
        message = f"aclpubcheck could not run: {detail}"
        return PubcheckResult(
            status="error",
            exit_code=None,
            summary=message,
            output=message,
            command_version=" ".join(executable),
        )

    output = "\n".join(
        part.strip() for part in (completed.stdout, completed.stderr) if part.strip()
    )
    status = _classify_result(completed.returncode, output)
    return PubcheckResult(
        status=status,
        exit_code=completed.returncode,
        summary=_summarize(output, status),
        output=output,
        command_version=" ".join(executable),
    )


def _summarize(output: str, status: str) -> str:
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if not lines:
        summary = f"aclpubcheck {status}"
    else:
        aggregate = next(
            (
                line
                for line in lines
                if line.startswith("We detected ") or line == "All Clear!"
            ),
            None,
        )
        detail = next(
            (
                line
                for line in lines
                if "Error (" in line or "Parsing Error" in line
            ),
            None,
        )
        if status == "pass":
            summary = aggregate or lines[-1]
        elif status == "fail":
            summary = " | ".join(part for part in (aggregate, detail) if part)
            summary = summary or lines[-1]
        else:
            summary = detail or lines[-1]
    home = str(Path.home())
    if home:
        summary = summary.replace(home, "<HOME>")
    if len(summary) > 500:
        summary = summary[:497] + "..."
    return summary


def _classify_result(exit_code: int, output: str) -> Literal["pass", "fail", "error"]:
    if exit_code != 0:
        return "error"
    if re.search(r"Parsing Error", output, flags=re.IGNORECASE):
        return "error"
    match = re.search(
        r"We detected\s+(\d+)\s+errors?\b", output, flags=re.IGNORECASE
    )
    if match:
        return "fail" if int(match.group(1)) else "pass"
    if "All Clear!" in output:
        return "pass"
    return "error"

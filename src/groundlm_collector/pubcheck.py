"""ACL pubcheck invocation and deterministic result classification."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
import subprocess
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
    status: Literal["pass", "fail"] = (
        "pass" if completed.returncode == 0 else "fail"
    )
    return PubcheckResult(
        status=status,
        exit_code=completed.returncode,
        summary=_summarize(output, status),
        output=output,
        command_version=" ".join(executable),
    )


def _summarize(output: str, status: str) -> str:
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    summary = lines[0] if lines else f"aclpubcheck {status}"
    home = str(Path.home())
    if home:
        summary = summary.replace(home, "<HOME>")
    if len(summary) > 500:
        summary = summary[:497] + "..."
    return summary

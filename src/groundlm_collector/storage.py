"""Atomic local storage and stable-number manifest handling."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import tempfile
from collections.abc import Callable, Iterable

from .models import ClassifiedSubmission


@dataclass(frozen=True, slots=True)
class Manifest:
    assignments: dict[str, str] = field(default_factory=dict)
    retired: dict[str, str] = field(default_factory=dict)
    files: dict[str, dict] = field(default_factory=dict)
    version: int = 1


@dataclass(frozen=True, slots=True)
class MaterializedPaper:
    pdf_path: str
    supplementary_paths: tuple[str, ...]
    file_metadata: dict[str, dict[str, str]]


def safe_filename(name: str, fallback: str) -> str:
    leaf = PurePosixPath(name.replace("\\", "/")).name
    leaf = re.sub(r"[\x00-\x1f\x7f/:]", "_", leaf).strip()
    if leaf in {"", ".", ".."}:
        leaf = fallback
    return leaf


def atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def load_manifest(path: Path) -> Manifest:
    if not path.exists():
        return Manifest()
    payload = json.loads(path.read_text(encoding="utf-8"))
    return Manifest(
        assignments={str(k): str(v) for k, v in payload.get("assignments", {}).items()},
        retired={str(k): str(v) for k, v in payload.get("retired", {}).items()},
        files=dict(payload.get("files", {})),
        version=int(payload.get("version", 1)),
    )


def save_manifest(path: Path, manifest: Manifest) -> None:
    data = json.dumps(
        asdict(manifest),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ).encode("utf-8") + b"\n"
    atomic_write_bytes(path, data)


def retire_absent_assignments(
    manifest: Manifest, active_forums: Iterable[str]
) -> Manifest:
    active = set(active_forums)
    assignments = {
        forum: number
        for forum, number in manifest.assignments.items()
        if forum in active
    }
    retired = dict(manifest.retired)
    retired.update(
        {
            forum: number
            for forum, number in manifest.assignments.items()
            if forum not in active
        }
    )
    return Manifest(
        assignments=assignments,
        retired=retired,
        files=dict(manifest.files),
        version=manifest.version,
    )


def materialize_paper(
    root: Path,
    number: str,
    record: ClassifiedSubmission,
    attachment_loader: Callable[[str, str], bytes],
) -> MaterializedPaper:
    if record.selection_status != "included":
        raise ValueError("Only included submissions can be materialized.")
    if "pdf" not in record.raw.attachments:
        raise ValueError(f"Submission {record.raw.forum} has no PDF attachment.")

    paper_directory = root / number
    pdf_data = attachment_loader(record.raw.note_id, "pdf")
    if not pdf_data.startswith(b"%PDF"):
        raise ValueError(f"Submission {record.raw.forum} did not return a valid PDF.")
    pdf_path = paper_directory / "paper.pdf"
    atomic_write_bytes(pdf_path, pdf_data)

    file_metadata: dict[str, dict[str, str]] = {
        "pdf": {
            "path": f"{root.name}/{number}/paper.pdf",
            "source": record.raw.attachments["pdf"],
            "sha256": hashlib.sha256(pdf_data).hexdigest(),
        }
    }
    supplementary_paths: list[str] = []
    used_names: set[str] = set()
    for field_name, remote_path in record.raw.attachments.items():
        if field_name == "pdf":
            continue
        suffix = PurePosixPath(remote_path).suffix or ".bin"
        base_name = safe_filename(field_name, "supplementary")
        candidate = safe_filename(f"{base_name}{suffix}", f"supplementary{suffix}")
        index = 2
        while candidate.casefold() in used_names:
            candidate = safe_filename(
                f"{base_name}_{index}{suffix}", f"supplementary_{index}{suffix}"
            )
            index += 1
        used_names.add(candidate.casefold())

        data = attachment_loader(record.raw.note_id, field_name)
        target = paper_directory / "supplementary" / candidate
        atomic_write_bytes(target, data)
        relative_path = f"{root.name}/{number}/supplementary/{candidate}"
        supplementary_paths.append(relative_path)
        file_metadata[field_name] = {
            "path": relative_path,
            "source": remote_path,
            "sha256": hashlib.sha256(data).hexdigest(),
        }

    return MaterializedPaper(
        pdf_path=f"{root.name}/{number}/paper.pdf",
        supplementary_paths=tuple(supplementary_paths),
        file_metadata=file_metadata,
    )

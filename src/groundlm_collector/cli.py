"""Command-line orchestration for metadata discovery and paper downloads."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Callable, Sequence

from .auth import create_client, load_keychain_credential
from .check_collection import check_collection
from .models import ClassifiedSubmission
from .openreview_source import discover_venue, download_attachment, fetch_submissions
from .report import PaperRow, write_csv
from .selection import (
    ARR_VENUE,
    DIRECT_VENUE,
    SHARED_TASK_VENUE,
    assign_numbers,
    find_duplicate_candidates,
    select_archival,
)
from .storage import (
    Manifest,
    MaterializedPaper,
    load_manifest,
    materialize_paper,
    save_manifest,
)


VENUE_IDS = (DIRECT_VENUE, ARR_VENUE, SHARED_TASK_VENUE)


@dataclass(frozen=True, slots=True)
class DownloadSummary:
    total: int
    included: int
    excluded: int
    needs_review: int
    downloaded: int
    skipped: int


def download_collection(
    client,
    *,
    project_root: Path,
    venue_ids: Sequence[str] = VENUE_IDS,
    dry_run: bool = False,
    progress: Callable[[str], None] | None = None,
) -> DownloadSummary:
    notify = progress or (lambda message: None)
    all_raw = []
    included: list[ClassifiedSubmission] = []
    excluded_count = 0
    needs_review: list[ClassifiedSubmission] = []

    for venue_id in venue_ids:
        schema = discover_venue(client, venue_id)
        raw_records = fetch_submissions(client, schema)
        selection = select_archival(raw_records)
        all_raw.extend(raw_records)
        included.extend(selection.included)
        excluded_count += len(selection.excluded)
        needs_review.extend(selection.needs_review)
        notify(
            f"metadata {venue_id}: total={len(raw_records)} "
            f"included={len(selection.included)} excluded={len(selection.excluded)} "
            f"needs_review={len(selection.needs_review)}"
        )

    if needs_review:
        forums = ", ".join(item.raw.forum for item in needs_review)
        raise RuntimeError(f"Ambiguous submissions require review: {forums}")

    duplicate_groups = find_duplicate_candidates([item.raw for item in included])
    if duplicate_groups:
        groups = ["/".join(item.forum for item in group) for group in duplicate_groups]
        raise RuntimeError(f"Possible cross-venue duplicates: {', '.join(groups)}")

    if dry_run:
        return DownloadSummary(
            total=len(all_raw),
            included=len(included),
            excluded=excluded_count,
            needs_review=0,
            downloaded=0,
            skipped=0,
        )

    papers_root = project_root / "all_papers"
    manifest_path = papers_root / "manifest.json"
    old_manifest = load_manifest(manifest_path)
    active_forums = {item.raw.forum for item in included}
    number_pool = {**old_manifest.retired, **old_manifest.assignments}
    number_pool = assign_numbers([item.raw for item in included], number_pool)
    assignments = {forum: number_pool[forum] for forum in active_forums}
    retired = dict(old_manifest.retired)
    retired.update(
        {
            forum: number
            for forum, number in old_manifest.assignments.items()
            if forum not in active_forums
        }
    )
    for forum in active_forums:
        retired.pop(forum, None)

    files = dict(old_manifest.files)
    working_manifest = Manifest(assignments=assignments, retired=retired, files=files)
    save_manifest(manifest_path, working_manifest)

    downloaded = 0
    skipped = 0
    materialized_by_forum: dict[str, MaterializedPaper] = {}
    ordered = sorted(included, key=lambda item: int(assignments[item.raw.forum]))
    for index, item in enumerate(ordered, start=1):
        number = assignments[item.raw.forum]
        existing = files.get(item.raw.forum, {})
        if _files_are_current(project_root, item, existing):
            materialized = _materialized_from_metadata(existing)
            skipped += 1
            notify(f"[{index}/{len(ordered)}] {number} cached {item.raw.title}")
        else:
            notify(f"[{index}/{len(ordered)}] {number} downloading {item.raw.title}")
            materialized = materialize_paper(
                papers_root,
                number,
                item,
                lambda note_id, field_name: download_attachment(
                    client, note_id, field_name
                ),
            )
            files[item.raw.forum] = materialized.file_metadata
            working_manifest = Manifest(
                assignments=assignments,
                retired=retired,
                files=files,
            )
            save_manifest(manifest_path, working_manifest)
            downloaded += 1
        materialized_by_forum[item.raw.forum] = materialized

    rows = [
        _paper_row(
            item,
            assignments[item.raw.forum],
            materialized_by_forum[item.raw.forum],
        )
        for item in ordered
    ]
    write_csv(project_root / "papers.csv", rows)
    return DownloadSummary(
        total=len(all_raw),
        included=len(included),
        excluded=excluded_count,
        needs_review=0,
        downloaded=downloaded,
        skipped=skipped,
    )


def _files_are_current(
    project_root: Path, item: ClassifiedSubmission, metadata: dict
) -> bool:
    if set(metadata) != set(item.raw.attachments):
        return False
    for field_name, remote_path in item.raw.attachments.items():
        entry = metadata.get(field_name, {})
        path = entry.get("path")
        if entry.get("source") != remote_path or not path:
            return False
        if not (project_root / path).is_file():
            return False
    return True


def _materialized_from_metadata(metadata: dict) -> MaterializedPaper:
    pdf_path = metadata["pdf"]["path"]
    supplementary = tuple(
        entry["path"]
        for field_name, entry in metadata.items()
        if field_name != "pdf"
    )
    return MaterializedPaper(
        pdf_path=pdf_path,
        supplementary_paths=supplementary,
        file_metadata=metadata,
    )


def _paper_row(
    item: ClassifiedSubmission, number: str, materialized: MaterializedPaper
) -> PaperRow:
    raw = item.raw
    return PaperRow(
        number=number,
        title=raw.title,
        authors=raw.authors,
        source_venue=raw.source_venue,
        track=item.track,
        openreview_submission_number=raw.number,
        decision=raw.decision or "",
        archival_status=item.archival_status,
        paper_type=item.paper_type or "",
        aclpubcheck_status="pending",
        aclpubcheck_summary="Not run",
        openreview_url=f"https://openreview.net/forum?id={raw.forum}",
        pdf_path=materialized.pdf_path,
        supplementary_files=materialized.supplementary_paths,
        aclpubcheck_pdf_sha256="",
        checked_at_utc="",
    )


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("download", help="Download archival papers and write CSV")
    subparsers.add_parser("dry-run", help="Show selection counts without writing files")
    check_parser = subparsers.add_parser(
        "check", help="Run incremental ACL publication checks and update CSV"
    )
    check_parser.add_argument(
        "--force", action="store_true", help="Recheck PDFs even when hashes match"
    )
    check_parser.add_argument(
        "--csv", type=Path, default=Path("papers.csv"), help="Paper report CSV"
    )
    check_parser.add_argument(
        "--logs-dir",
        type=Path,
        default=Path("aclpubcheck-logs"),
        help="Directory for full per-paper checker logs",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    project_root = Path.cwd()
    if args.command == "check":
        csv_path = args.csv if args.csv.is_absolute() else project_root / args.csv
        logs_dir = (
            args.logs_dir
            if args.logs_dir.is_absolute()
            else project_root / args.logs_dir
        )
        summary = check_collection(
            csv_path,
            project_root,
            logs_dir,
            force=args.force,
        )
        print(
            f"complete total={summary.total} checked={summary.checked} "
            f"skipped={summary.skipped} passed={summary.passed} "
            f"failed={summary.failed} errors={summary.errors} "
            f"needs_review={summary.needs_review}",
            flush=True,
        )
        return 0

    client = create_client(load_keychain_credential())
    summary = download_collection(
        client,
        project_root=project_root,
        dry_run=args.command == "dry-run",
        progress=lambda message: print(message, flush=True),
    )
    print(
        f"complete total={summary.total} included={summary.included} "
        f"excluded={summary.excluded} downloaded={summary.downloaded} "
        f"cached={summary.skipped}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

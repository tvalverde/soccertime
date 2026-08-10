"""Snapshot creation and generational pruning for the production backups.

Deliberately free of Django imports so it can run in a bare container, without the
settings a management command would need:

    python -m soccertime.backups snapshot-db /db/db.sqlite3 /backups/db.20260810_203027.sqlite3.gz
    python -m soccertime.backups prune /backups --keep-last 3 --keep-daily 7 --keep-monthly 12

Retention is generational rather than a plain count, because a plain count measures
history in deploys instead of in time: six deploys in one afternoon evicted five months
of restore points, and the data problem they were needed for had gone unnoticed since
March.
"""

import argparse
import gzip
import re
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

SNAPSHOT_PATTERN = re.compile(r"^(?P<group>[a-z-]+)\.(?P<timestamp>\d{8}_\d{6})\.")
TIMESTAMP_FORMAT = "%Y%m%d_%H%M%S"


def parse_snapshot(name):
    """Return (group, datetime) for a snapshot filename, or None if it is not one."""
    match = SNAPSHOT_PATTERN.match(name)
    if not match:
        return None
    try:
        return match["group"], datetime.strptime(match["timestamp"], TIMESTAMP_FORMAT)
    except ValueError:
        return None


def select_kept(names, keep_last, keep_daily, keep_monthly):
    """Names to preserve: the newest few, plus one per recent day and per recent month.

    Each tier is computed over the snapshots that exist, so a quiet week simply has no
    daily entry rather than reaching further back to invent one.
    """
    snapshots = [(name, parsed[1]) for name in names if (parsed := parse_snapshot(name))]
    snapshots.sort(key=lambda item: item[1], reverse=True)

    kept = {name for name, _ in snapshots[:keep_last]}

    for attribute, limit in (("%Y%m%d", keep_daily), ("%Y%m", keep_monthly)):
        newest_per_period = {}
        for name, moment in snapshots:
            newest_per_period.setdefault(moment.strftime(attribute), name)
        for period in sorted(newest_per_period, reverse=True)[:limit]:
            kept.add(newest_per_period[period])

    return kept


def prune(directory, keep_last, keep_daily, keep_monthly, dry_run=False):
    """Delete expired snapshots, keeping each group (db, media, ...) independently."""
    directory = Path(directory)
    groups = {}
    for path in directory.iterdir():
        parsed = parse_snapshot(path.name)
        if parsed:
            groups.setdefault(parsed[0], []).append(path.name)

    removed = []
    for group, names in sorted(groups.items()):
        kept = select_kept(names, keep_last, keep_daily, keep_monthly)
        for name in sorted(set(names) - kept):
            removed.append(f"{group}/{name}")
            if not dry_run:
                (directory / name).unlink()
    return removed


def snapshot_database(source, destination):
    """Write a consistent, compressed copy of a live SQLite database.

    Copying the file byte by byte can capture a half-written transaction; the backup API
    takes a coherent snapshot even while the application is writing.
    """
    destination = Path(destination)
    uncompressed = destination.with_suffix("")

    source_connection = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    target_connection = sqlite3.connect(uncompressed)
    try:
        source_connection.backup(target_connection)
    finally:
        target_connection.close()
        source_connection.close()

    with open(uncompressed, "rb") as raw, gzip.open(destination, "wb") as compressed:
        shutil.copyfileobj(raw, compressed)
    uncompressed.unlink()
    return destination


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    snapshot = subparsers.add_parser("snapshot-db", help="Write a consistent compressed database copy")
    snapshot.add_argument("source")
    snapshot.add_argument("destination")

    pruner = subparsers.add_parser("prune", help="Apply the generational retention policy")
    pruner.add_argument("directory")
    pruner.add_argument("--keep-last", type=int, default=3)
    pruner.add_argument("--keep-daily", type=int, default=7)
    pruner.add_argument("--keep-monthly", type=int, default=12)
    pruner.add_argument("--dry-run", action="store_true")

    args = parser.parse_args(argv)

    if args.command == "snapshot-db":
        destination = snapshot_database(args.source, args.destination)
        print(f"Snapshot written: {destination.name} ({destination.stat().st_size / 1_048_576:.1f} MB)")
        return

    removed = prune(args.directory, args.keep_last, args.keep_daily, args.keep_monthly, args.dry_run)
    for name in removed:
        print(f"{'Would prune' if args.dry_run else 'Pruned'}: {name}")
    print(f"Snapshots pruned: {len(removed)}")


if __name__ == "__main__":
    main()

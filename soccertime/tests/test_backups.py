"""Tests for the generational retention policy and the database snapshot."""

import gzip
import sqlite3

import pytest

from soccertime.backups import parse_snapshot, prune, select_kept, snapshot_database


def names(*timestamps, group="db"):
    return [f"{group}.{stamp}.sqlite3.gz" for stamp in timestamps]


class TestParseSnapshot:
    def test_reads_group_and_moment(self):
        group, moment = parse_snapshot("db.20260810_203027.sqlite3.gz")
        assert group == "db"
        assert (moment.year, moment.month, moment.day, moment.hour) == (2026, 8, 10, 20)

    @pytest.mark.parametrize(
        "name",
        ["db.sqlite3", "db.2026081_203027.sqlite3.gz", "db.20261332_203027.sqlite3.gz", "notes.txt"],
    )
    def test_ignores_anything_that_is_not_a_snapshot(self, name):
        assert parse_snapshot(name) is None


class TestSelectKept:
    def test_a_burst_of_deploys_cannot_evict_older_history(self):
        """The failure this policy exists for: six deploys in one afternoon.

        Under a plain count they would have been the only survivors, which is how a
        five-month-old restore point was lost.
        """
        burst = names(*[f"20260810_20{minute:02d}00" for minute in range(30, 36)])
        history = names("20260307_145026", "20260601_120000", "20260715_120000")

        kept = select_kept(burst + history, keep_last=3, keep_daily=7, keep_monthly=12)

        assert set(history) <= kept
        assert len(kept & set(burst)) == 3

    def test_keeps_one_per_day_for_the_recent_days(self):
        daily = names(*[f"202608{day:02d}_120000" for day in range(1, 11)])
        extra_same_day = names("20260810_090000")

        kept = select_kept(daily + extra_same_day, keep_last=1, keep_daily=7, keep_monthly=0)

        assert "db.20260810_120000.sqlite3.gz" in kept
        assert "db.20260810_090000.sqlite3.gz" not in kept, "only the newest of each day survives"
        assert len(kept) == 7

    def test_keeps_one_per_month_for_the_recent_months(self):
        monthly = names(*[f"2026{month:02d}15_120000" for month in range(1, 9)])

        kept = select_kept(monthly, keep_last=0, keep_daily=0, keep_monthly=3)

        assert kept == set(names("202608" + "15_120000", "20260715_120000", "20260615_120000"))

    def test_tiers_overlap_without_inflating_the_count(self):
        kept = select_kept(names("20260810_120000"), keep_last=3, keep_daily=7, keep_monthly=12)
        assert kept == {"db.20260810_120000.sqlite3.gz"}

    def test_empty_input(self):
        assert select_kept([], keep_last=3, keep_daily=7, keep_monthly=12) == set()


class TestPrune:
    def test_groups_are_kept_independently(self, tmp_path):
        for group in ("db", "media"):
            for day in range(1, 6):
                (tmp_path / f"{group}.202608{day:02d}_120000.tgz").write_text("x")

        removed = prune(tmp_path, keep_last=2, keep_daily=0, keep_monthly=0)

        assert len(removed) == 6
        assert sorted(p.name for p in tmp_path.iterdir()) == [
            "db.20260804_120000.tgz",
            "db.20260805_120000.tgz",
            "media.20260804_120000.tgz",
            "media.20260805_120000.tgz",
        ]

    def test_leaves_unrelated_files_alone(self, tmp_path):
        (tmp_path / "README").write_text("x")
        (tmp_path / "db.20260101_120000.tgz").write_text("x")
        (tmp_path / "db.20260810_120000.tgz").write_text("x")

        prune(tmp_path, keep_last=1, keep_daily=0, keep_monthly=0)

        assert (tmp_path / "README").exists()

    def test_dry_run_deletes_nothing(self, tmp_path):
        for day in (1, 2, 3):
            (tmp_path / f"db.202608{day:02d}_120000.tgz").write_text("x")

        removed = prune(tmp_path, keep_last=1, keep_daily=0, keep_monthly=0, dry_run=True)

        assert len(removed) == 2
        assert len(list(tmp_path.iterdir())) == 3


class TestSnapshotDatabase:
    def test_writes_a_readable_compressed_copy(self, tmp_path):
        source = tmp_path / "live.sqlite3"
        connection = sqlite3.connect(source)
        connection.execute("create table event (name text)")
        connection.execute("insert into event values ('final')")
        connection.commit()

        destination = snapshot_database(source, tmp_path / "db.20260810_120000.sqlite3.gz")

        restored = tmp_path / "restored.sqlite3"
        with gzip.open(destination, "rb") as compressed:
            restored.write_bytes(compressed.read())
        assert sqlite3.connect(restored).execute("select name from event").fetchone() == ("final",)

    def test_snapshot_is_consistent_while_a_transaction_is_open(self, tmp_path):
        """A byte-for-byte copy can capture a half-written transaction; this must not."""
        source = tmp_path / "live.sqlite3"
        connection = sqlite3.connect(source, isolation_level=None)
        connection.execute("create table event (name text)")
        connection.execute("insert into event values ('committed')")
        connection.execute("begin")
        connection.execute("insert into event values ('uncommitted')")

        destination = snapshot_database(source, tmp_path / "db.20260810_120000.sqlite3.gz")

        restored = tmp_path / "restored.sqlite3"
        with gzip.open(destination, "rb") as compressed:
            restored.write_bytes(compressed.read())
        rows = [row[0] for row in sqlite3.connect(restored).execute("select name from event")]
        assert rows == ["committed"]

    def test_leaves_no_uncompressed_copy_behind(self, tmp_path):
        source = tmp_path / "live.sqlite3"
        sqlite3.connect(source).execute("create table event (name text)")

        snapshot_database(source, tmp_path / "db.20260810_120000.sqlite3.gz")

        assert not (tmp_path / "db.20260810_120000.sqlite3").exists()

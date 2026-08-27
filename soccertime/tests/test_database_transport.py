"""How the database is moved between machines, once it keeps a write-ahead log.

WAL splits the database across two files: the newest committed transactions live in
`db.sqlite3-wal` until a checkpoint folds them back, and nothing promises when that is. Two
rules follow, and neither is visible at the point where it is broken.

The first is that a copy has to be taken *through* a connection — `snapshot_database` does,
`cp` does not, and `test_backups.py` demonstrates the row a `cp` loses rather than asserting
it from memory. A backup missing its last hour raises nothing and looks exactly like a good
one; it is discovered the day it is restored.

The second is that a database file may not be replaced while a log from the previous one is
still lying beside it. SQLite would read that log as belonging to the new file. That is not a
stale backup, it is a corrupt database, and it is the reason these targets stop the service
before they write rather than restarting it afterwards.

Asserted against the `Makefile` itself because that is where the production operations of
this project live — the same reason `test_requirements.py` reads `requirements.txt` and
`test_compose_images.py` reads the compose files.
"""

from pathlib import Path

import pytest

MAKEFILE = Path(__file__).resolve().parents[2] / "Makefile"

# Every target that puts a different database where a live one was.
REPLACING_TARGETS = ["download-db", "upload-db", "restore-remote-db"]


def recipe(target: str) -> str:
    """The commands `make <target>` would run, as one string."""
    collected: list[str] = []
    inside = False
    for line in MAKEFILE.read_text().splitlines():
        if line.startswith(f"{target}:"):
            inside = True
            continue
        if inside:
            if line.startswith("\t") or not line.strip():
                collected.append(line)
            else:
                break
    return "\n".join(collected)


class TestTheMakefileIsReadable:
    """Guards the parser: a test reading nothing would assert nothing."""

    @pytest.mark.parametrize("target", REPLACING_TARGETS)
    def test_each_target_has_a_recipe(self, target):
        assert recipe(target).strip()


class TestTheDatabaseTravelsThroughAConnection:
    def test_downloading_it_uses_the_online_backup(self):
        """`cp` of the main file leaves behind whatever is still in the log."""
        assert "snapshot-db" in recipe("download-db")

    @pytest.mark.parametrize("target", REPLACING_TARGETS)
    def test_no_target_copies_the_database_file_by_hand(self, target):
        commands = recipe(target)

        assert "cp /from/$(REMOTE_DB_FILE_IN_VOLUME)" not in commands
        assert "cp /data/$(REMOTE_DB_FILE_IN_VOLUME)" not in commands
        assert "cp /db/$(REMOTE_DB_FILE_IN_VOLUME)" not in commands
        assert "cp $(LOCAL_DB_PATH)" not in commands


class TestAReplacedDatabaseLeavesNoLogBehind:
    @pytest.mark.parametrize("target", REPLACING_TARGETS)
    def test_the_log_and_the_shared_index_are_removed(self, target):
        """A log from the previous database, read as belonging to the new one, corrupts it."""
        commands = recipe(target)

        assert "-wal" in commands
        assert "-shm" in commands

    @pytest.mark.parametrize("target", ["upload-db", "restore-remote-db"])
    def test_the_service_is_stopped_before_the_file_is_written(self, target):
        """Restarting afterwards is not the same: the running process holds the old file open."""
        commands = recipe(target)

        assert "stop $(REMOTE_SOCCERTIME_SERVICE)" in commands

"""How the database journals its writes, and what that buys.

Under the default rollback journal a writer takes an exclusive lock over the whole file, so
every reader waits for it and then gives up with `database is locked`. That was survivable
while the pages were served from an hour-long cache and the only writer was the hourly
scrape: the two rarely met. The API changed that — it is not cached, so every request goes
to the database — which is what makes the journal worth changing rather than a detail.

**The suite runs against `file:memorydb_default?mode=memory&cache=shared`, and a
write-ahead log does not exist for an in-memory database**: `PRAGMA journal_mode=WAL` there
answers "memory" and changes nothing. Asserting the journal on the suite's own connection
would therefore have passed while testing nothing — the exact shape of test this project
has already been bitten by. So every test here opens a real file, through a connection
configured from the settings the application ships.
"""

import sqlite3

import pytest
from django.db import connections
from django.db.backends.sqlite3.base import DatabaseWrapper


@pytest.fixture
def database_path(tmp_path):
    return tmp_path / "db.sqlite3"


@pytest.fixture
def application_connection(database_path, django_db_blocker):
    """A connection opened exactly as the application opens its own, over a file on disk.

    Unblocked explicitly: pytest-django refuses any connection that is not the suite's own,
    and this one deliberately is not — the suite's is in memory, where the journal under
    test does not exist. Nothing here touches the application database.
    """
    with django_db_blocker.unblock():
        wrapper = DatabaseWrapper({**connections["default"].settings_dict, "NAME": str(database_path)})
        with wrapper.cursor() as cursor:
            cursor.execute("CREATE TABLE event (name TEXT);")
            cursor.execute("INSERT INTO event VALUES ('kick off');")
        yield wrapper
        wrapper.close()


def pragma(wrapper, name):
    with wrapper.cursor() as cursor:
        cursor.execute(f"PRAGMA {name};")
        return cursor.fetchone()[0]


class TestTheJournalTheApplicationOpensWith:
    def test_it_is_a_write_ahead_log(self, application_connection):
        assert pragma(application_connection, "journal_mode") == "wal"

    def test_the_log_is_left_beside_the_database(self, application_connection, database_path):
        """Which is why every path that copies or replaces the file has to know about it."""
        assert database_path.with_name(f"{database_path.name}-wal").exists()

    def test_writes_are_flushed_at_the_point_the_log_makes_safe(self, application_connection):
        """`NORMAL` (1), not `FULL` (2).

        With a write-ahead log this survives anything the application can do to itself — a
        crash, an OOM kill, a container stopped mid-write. Only the machine losing power can
        cost the last transactions, and this database is rebuilt from the source every hour.
        """
        assert pragma(application_connection, "synchronous") == 1

    def test_a_reader_waits_before_giving_up(self, application_connection):
        assert pragma(application_connection, "busy_timeout") == 20000


class TestAWriterNoLongerBlocksAReader:
    """The property the whole change exists for, exercised rather than asserted."""

    def read_count(self, database_path, timeout=0.5):
        reader = sqlite3.connect(database_path, timeout=timeout)
        try:
            return reader.execute("SELECT COUNT(*) FROM event;").fetchone()[0]
        finally:
            reader.close()

    def test_a_read_succeeds_while_a_write_transaction_is_held_open(self, application_connection, database_path):
        """Under the rollback journal this is where the API answered 500 to a scrape."""
        writer = sqlite3.connect(database_path, isolation_level=None)
        writer.execute("BEGIN EXCLUSIVE;")
        writer.execute("INSERT INTO event VALUES ('while the scraper writes');")
        try:
            counted = self.read_count(database_path)
        finally:
            writer.execute("ROLLBACK;")
            writer.close()

        assert counted == 1

    def test_the_reader_sees_the_write_once_it_lands(self, application_connection, database_path):
        """And it is the committed state it sees, not a half-written one."""
        writer = sqlite3.connect(database_path, isolation_level=None)
        writer.execute("BEGIN EXCLUSIVE;")
        writer.execute("INSERT INTO event VALUES ('committed');")
        writer.execute("COMMIT;")
        writer.close()

        assert self.read_count(database_path) == 2

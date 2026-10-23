"""The targets that install a crontab entry hand the installer the arguments they name.

`scripts/install-cron-entry.sh` reaches the server as standard input to `ssh '<host> sh -s
<marker> <schedule> <command>'`, and `sh` reads its own options before the positional
arguments. A marker that starts with a dash — `--source=tokyo` is the one that does — is
therefore taken for an option of `sh` itself, and dash refuses it with "Illegal option --"
before a line of the installer has run. That is how the change of the `tokyo` list's URL on
2026-10-23 failed: the target had been broken since the marker became `--source=...`, and
nothing ran it until the list moved.

So each recipe's remote command is run here as the server would run it, by `/bin/sh` with
the installer on its standard input, against a stand-in `crontab` writing to a file. What
is asserted is the outcome — the entry ends up in the crontab — not the spelling of the fix.
"""

import os
import re
import stat
import subprocess
from pathlib import Path

import pytest

from soccertime.tests.test_database_transport import MAKEFILE, recipe

INSTALLER = MAKEFILE.parent / "scripts" / "install-cron-entry.sh"

# Every target whose recipe pipes the installer to the server.
CRON_TARGETS = ["remote-install-import-cron", "remote-install-logrotate"]

FAKE_CRONTAB = """#!/bin/sh
case "$1" in
    -l) cat "$CRONTAB_FILE" ;;
    -) cat > "$CRONTAB_FILE" ;;
    *) exit 2 ;;
esac
"""

SAMPLE_VALUES = {
    "SOURCE": "tokyo",
    "CRON_SCHEDULE": "20 1,7,13,19 * * *",
    "IMPORT_CRON_COMMAND": "python manage.py addlinksource --source=tokyo --url=https://example.org/list.m3u",
    "LOGROTATE_SCHEDULE": "45 3 * * *",
    "LOGROTATE_CRON_COMMAND": "/usr/sbin/logrotate --state ~/logrotate/soccertime.state ~/logrotate/soccertime.conf",
}


def remote_command(target: str) -> str:
    """The command the target asks the server's shell to run, with sample values in place."""
    match = re.search(r"'(sh -s [^']*)' < scripts/install-cron-entry\.sh", recipe(target))
    assert match, f"{target} no longer pipes the installer"
    return re.sub(r"\$\((\w+)\)", lambda variable: SAMPLE_VALUES[variable.group(1)], match.group(1))


@pytest.fixture
def server(tmp_path: Path) -> dict[str, str]:
    """An environment whose `crontab` keeps the deploy user's table in a file."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    crontab = bin_dir / "crontab"
    crontab.write_text(FAKE_CRONTAB)
    crontab.chmod(crontab.stat().st_mode | stat.S_IXUSR)
    table = tmp_path / "crontab.txt"
    table.write_text("4 */4 * * * python manage.py scrapit\n")
    return {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}", "CRONTAB_FILE": str(table)}


@pytest.mark.parametrize("target", CRON_TARGETS)
def test_the_installer_receives_the_entry_it_is_handed(target, server):
    with INSTALLER.open("rb") as installer:
        result = subprocess.run(
            ["/bin/sh", "-c", remote_command(target)], stdin=installer, env=server, capture_output=True, text=True
        )

    assert result.returncode == 0, result.stderr
    table = Path(server["CRONTAB_FILE"]).read_text()
    assert "python manage.py scrapit" in table
    assert any(SAMPLE_VALUES[name] in table for name in ("IMPORT_CRON_COMMAND", "LOGROTATE_CRON_COMMAND"))

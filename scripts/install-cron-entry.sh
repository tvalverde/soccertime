# Install, or refresh, one entry in the deploy user's crontab without disturbing the rest.
#
# Run from the Makefile — the `remote-install-*` targets pipe it to the server over
# `ssh 'sh -s'`, the same way `relay.sh` is run. POSIX sh on purpose: there is no shebang
# to honour under `sh -s`, so nothing here may assume bash.
#
#   sh -s <marker> <schedule> <command>
#
# Idempotent by marker: every existing line containing that fixed string is dropped before
# the new entry is appended, so re-running after a schedule or URL change leaves exactly
# one. Every other line is copied through byte for byte — comments and the scraper's own
# entry included, which is the one thing this must never disturb. The marker therefore has
# to be something no other entry can contain: `--source=tokyo`, not `python`.

set -eu

MARKER="${1:?usage: install-cron-entry.sh <marker> <schedule> <command>}"
SCHEDULE="${2:?usage: install-cron-entry.sh <marker> <schedule> <command>}"
COMMAND="${3:?usage: install-cron-entry.sh <marker> <schedule> <command>}"

# cron reads an unescaped % as a newline and hands what follows to the command's stdin,
# which would quietly truncate any URL carrying a percent-encoded character.
escaped_command=$(printf '%s' "$COMMAND" | sed 's/%/\\%/g')
ENTRY="$SCHEDULE $escaped_command"

# A crontab that does not exist yet makes `crontab -l` fail; an empty one is the same
# starting point, so that failure is not worth propagating under `set -e`.
current=$(crontab -l 2>/dev/null || true)
kept=$(printf '%s\n' "$current" | grep -vF -- "$MARKER" || true)

if [ -n "$kept" ]; then
    printf '%s\n%s\n' "$kept" "$ENTRY" | crontab -
else
    printf '%s\n' "$ENTRY" | crontab -
fi

echo "--- crontab now reads ---"
crontab -l

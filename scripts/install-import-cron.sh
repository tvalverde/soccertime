# Install a periodic link import into the deploy user's crontab, without disturbing it.
#
# Run from the Makefile — `remote-install-import-cron` pipes it to the server over
# `ssh 'sh -s'`, the same way `relay.sh` is run. POSIX sh on purpose: there is no shebang
# to honour under `sh -s`, so nothing here may assume bash.
#
#   sh -s <source> <url> <schedule>
#
# Idempotent by the source name: a line already importing that source is replaced rather
# than added, so re-running after a schedule or URL change leaves exactly one entry. Every
# other line is copied through byte for byte — comments and the scraper's own entry
# included, which is the one thing this must never disturb.
#
# `docker compose exec` without `-T` is deliberate, matching the scraper's entry that has
# been running from this crontab for months. It is the proven invocation on this host.

set -eu

SOURCE="${1:?usage: install-import-cron.sh <source> <url> <schedule>}"
URL="${2:?usage: install-import-cron.sh <source> <url> <schedule>}"
SCHEDULE="${3:?usage: install-import-cron.sh <source> <url> <schedule>}"

# cron reads an unescaped % as a newline and hands what follows to the command's stdin,
# which would quietly truncate any URL carrying a percent-encoded character.
escaped_url=$(printf '%s' "$URL" | sed 's/%/\\%/g')

COMMAND="docker compose -f ./docker/docker-compose.yml exec --user appuser soccertime-web \
python manage.py addlinksource --source=$SOURCE --url=$escaped_url >> ~/addlinksource-$SOURCE.log 2>&1"
ENTRY="$SCHEDULE $COMMAND"

# A crontab that does not exist yet makes `crontab -l` fail; an empty one is the same
# starting point, so that failure is not worth propagating under `set -e`.
current=$(crontab -l 2>/dev/null || true)
kept=$(printf '%s\n' "$current" | grep -v -- "--source=$SOURCE" || true)

if [ -n "$kept" ]; then
    printf '%s\n%s\n' "$kept" "$ENTRY" | crontab -
else
    printf '%s\n' "$ENTRY" | crontab -
fi

echo "--- crontab now reads ---"
crontab -l

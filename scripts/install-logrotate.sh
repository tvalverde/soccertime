# Write the deploy user's logrotate configuration for the logs its cron entries append to.
#
# Run from the Makefile — `remote-install-logrotate` pipes it to the server over
# `ssh 'sh -s'`, the same way `relay.sh` is run. POSIX sh on purpose: there is no shebang
# to honour under `sh -s`, so nothing here may assume bash.
#
#   sh -s <log-name> [<log-name>...]      names relative to the home directory
#
# Nothing here needs root. The system's own logrotate reads /etc/logrotate.d, which the
# deploy user cannot write, so this configuration is driven by a crontab entry of its own
# carrying `--state` — that flag is the whole reason a rootless rotation is possible, since
# the default state file lives under /var/lib.
#
# Rotation renames the file and creates a new one, which is safe precisely because each
# cron run opens its log with `>>` and closes it on the way out: nothing holds a descriptor
# between runs. `delaycompress` covers the one case that is not instantaneous — a scrape
# still writing when the rotation lands keeps writing to the renamed file, and compressing
# it a cycle later means those lines are not lost into a gzip stream that was already
# closed.

set -eu

[ "$#" -gt 0 ] || { echo "usage: install-logrotate.sh <log-name> [<log-name>...]" >&2; exit 1; }

CONFIG_DIR="$HOME/logrotate"
CONFIG="$CONFIG_DIR/soccertime.conf"

mkdir -p "$CONFIG_DIR"

{
    for log in "$@"; do
        printf '%s\n' "$HOME/$log"
    done
    # `create` without a mode keeps whatever the log already had, so the deploy user's
    # ownership is preserved without this file having to know its name.
    cat <<'CONFIG_BODY'
{
    weekly
    maxsize 5M
    rotate 8
    compress
    delaycompress
    missingok
    notifempty
    create
}
CONFIG_BODY
} > "$CONFIG"

echo "--- $CONFIG ---"
cat "$CONFIG"

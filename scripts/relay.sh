# Hand the service over to a freshly built image without dropping the site.
#
# Run from the Makefile — `remote_deploy` pipes it to the server over `ssh 'sh -s'`, and
# `replica-relay` runs this same file against the local replica, which is what makes the
# rehearsal and the production path one piece of code. POSIX sh on purpose: there is no
# shebang to honour under `sh -s`, so nothing here may assume bash.
#
#   sh -s <service> <expected-image-tag>
#   environment: COMPOSE_CMD, HEALTH_TIMEOUT, PROXY_SETTLE_SECONDS
#
# The promise this script makes is single: when it exits 0, exactly one container of the
# service is serving and it runs the image named by <expected-image-tag>. Its predecessor
# assumed exactly one container was already running, and broke silently either side of
# that: with two left behind by an interrupted deploy, `--scale=2` created nothing, the
# "new" container it waited on was really the second old one, and the deploy reported
# success with the freshly built image never having run. With zero, it started two and
# seeded that same state for every deploy after it.

set -eu

SERVICE="${1:?usage: relay.sh <service> <expected-image-tag>}"
IMAGE_TAG="${2:?usage: relay.sh <service> <expected-image-tag>}"
: "${COMPOSE_CMD:?COMPOSE_CMD must hold the docker compose invocation}"
: "${HEALTH_TIMEOUT:=90}"
: "${PROXY_SETTLE_SECONDS:=5}"

say() { echo "$@"; }

# --- 1. Take stock, and heal a state a previous interruption left behind ---------------
# Two containers are never a valid steady state here — the page cache is per-container,
# so a second one serves stale pages — and any extras are by construction superseded
# copies. All but the newest are retired, loudly, before anything else happens; the
# newest keeps serving through the relay, so healing costs no downtime.
# `.Created` is ISO 8601, so lexicographic sort is chronological sort — no shell string
# comparison needed, which matters because `[ a \> b ]` is not POSIX and this runs under
# whatever `sh` the server has.
running=$($COMPOSE_CMD ps -q "$SERVICE")
old=""
if [ -n "$running" ]; then
    old=$(for id in $running; do
        echo "$(docker inspect -f '{{.Created}}' "$id") $id"
    done | sort | tail -1 | awk '{print $2}')
    for id in $running; do
        [ "$id" = "$old" ] && continue
        say "  found a stale extra container left by an interrupted deploy; retiring $(echo "$id" | cut -c1-12)"
        docker stop -t 20 "$id" >/dev/null && docker rm "$id" >/dev/null
        say "  healed: $(echo "$old" | cut -c1-12) kept serving"
    done
fi

# --- 2. Resolve what this run promises to put into service ----------------------------
expected=$(docker image inspect "$IMAGE_TAG" -f '{{.Id}}') || {
    say "ERROR: the image $IMAGE_TAG does not exist here; build it first"; exit 1;
}


# --- 3. Start the new container beside the old one (or alone, if none) -----------------
if [ -n "$old" ]; then
    say "--- Starting the new container beside the one still serving ---"
    $COMPOSE_CMD up -d --no-recreate --remove-orphans --scale "$SERVICE=2" "$SERVICE"
else
    say "--- Nothing is serving; starting the new container on its own ---"
    $COMPOSE_CMD up -d --remove-orphans "$SERVICE"
fi

new=""
for id in $($COMPOSE_CMD ps -q "$SERVICE"); do
    [ "$id" = "$old" ] || new="$id"
done

# --- 4. Assert the promise, before anything is waited on or retired --------------------
# This is the line that makes the old silent failure impossible to express: whatever else
# happens, exit 0 now implies the built image is the one serving.
if [ -z "$new" ]; then
    say "ERROR: no new container appeared; the old one is untouched and still serving"
    exit 1
fi
actual=$(docker inspect -f '{{.Image}}' "$new")
if [ "$actual" != "$expected" ]; then
    say "ERROR: the new container runs $actual, not the just-built $expected"
    say "       removing it; the old container is untouched and still serving"
    docker rm -f "$new" >/dev/null
    exit 1
fi

# --- 5. Wait for it to answer before the old one goes anywhere -------------------------
say "--- Waiting for it to answer before retiring the old one ---"
deadline=$(( $(date +%s) + HEALTH_TIMEOUT ))
until docker exec "$new" python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz/')" >/dev/null 2>&1; do
    if [ "$(date +%s)" -ge "$deadline" ]; then
        say "  the new container never answered; removing it and leaving the old one serving"
        docker rm -f "$new" >/dev/null
        exit 1
    fi
    sleep 1
done

# Traefik 3 marks a newly discovered server down until its first probe succeeds, so a
# container that answers is not yet receiving traffic. Retiring the old one now would
# leave the router with no live server — 502, then the route itself withdrawn. Five probe
# intervals is the margin that removed it, measured.
say "  the new container is serving, giving the proxy time to see that too"
sleep "$PROXY_SETTLE_SECONDS"

# --- 6. Retire the predecessor ---------------------------------------------------------
if [ -n "$old" ]; then
    say "--- Retiring the previous container ---"
    docker stop -t 20 "$old" >/dev/null && docker rm "$old" >/dev/null
fi

# --- 7. Post-condition: say what is true, having made it true --------------------------
remaining=$($COMPOSE_CMD ps -q "$SERVICE")
count=$(echo "$remaining" | grep -c . || true)
if [ "$count" -ne 1 ] || [ "$(docker inspect -f '{{.Image}}' "$remaining")" != "$expected" ]; then
    say "ERROR: post-condition failed — $count container(s) running, expected exactly 1 on $IMAGE_TAG"
    exit 1
fi
say "  handover complete: $(echo "$remaining" | cut -c1-12) serving $IMAGE_TAG"

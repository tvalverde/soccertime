# Soccertime — instructions for Claude Code

**Read `AGENTS.md` first.** It holds the project conventions: stack, testing rules,
the mandatory `CHANGELOG.md` entry after every change, and the Ruff commands. The other
CLIs load it automatically; Claude Code does not, so it is easy to work a whole session
without ever seeing it. That is exactly how the changelog went unmaintained.

## Verify the failing path, not the working one

Two production outages in one session came from the same mistake: testing the state the
local environment happens to be in, rather than the states production is actually in.

- Local media is complete. Production had 49 flag rows whose file was gone. Declaring
  `width_field` on the image fields made Django read the file on `post_init`, so merely
  loading those rows raised `FileNotFoundError` and `/competitions/` returned 500.
- HTTPS traffic arrives through Traefik carrying `X-Forwarded-Proto`. The container
  health check does not. Enabling `SECURE_SSL_REDIRECT` answered it with a 301, the check
  failed, the container was marked unhealthy and the proxy withdrew the route, so every
  page returned 404.

Before deploying anything that touches stored data or request handling, list the states
production can hold that local cannot — missing files, null columns, rows written by
older code, callers that bypass the proxy — and exercise them. Querying production
read-only first is cheap, and it is what made the `ChannelLink` unique constraint land
without incident: counting duplicates beforehand showed there were none.

When a test only passes because the environment is clean, it is not a regression test.
Confirm a new test fails without the fix.

## A deploy is not verified until the container is healthy

`make deploy-production` reported "completed successfully" both times the site was
broken. After every deploy: wait for the container to report `healthy`, fetch the real
pages, and check the logs for 500s. `make remote-check` must come back clean. Pages are
cached for an hour, so use `make remote-clear-cache` before concluding anything from a
page fetch.

`healthy` is not the same as working. `/healthz/` returns JSON and renders no template, so
it stays green through failures that break every real page. That is exactly what happened
when static filenames gained a content hash: `collectstatic` ran after `up -d`, the new
process read a manifest that was not finished, cached it for its whole life, and answered
500 to every page while the health check passed and the container reported healthy. Only
the smoke test caught it. Anything that a page renders but `healthz` does not — templates,
static files, context processors — needs a real page fetched before a deploy is believed.

## The development container caches templates

Editing a template and taking a screenshot shows the *previous* markup: the running process
holds the compiled template and only a `docker compose restart web` picks the change up.
Static files are served fresh, so a CSS edit appears immediately and a template edit does
not, which is exactly the combination that makes a stale page look like a working one. It
already produced one false negative — a collapse that appeared not to open. Restart before
believing a capture, and add a query string so the browser does not answer from its own
cache either.

## Django specifics this project has already paid for

- Never declare `width_field` / `height_field` on an `ImageField` here: they hook
  `update_dimension_fields` to `post_init`, which reads the file. `save_image` records
  the dimensions from the buffer instead.
- `SECURE_SSL_REDIRECT` needs `SECURE_REDIRECT_EXEMPT` for `healthz`.
- Data migrations run against *historical* models, which can still carry field options a
  later migration removes. Read with `values_list` and write with `update` so no model
  instance — and no `post_init` handler — is ever built.
- Views are wrapped in `@cache_page`. Never put per-request state into a cached response:
  a `messages` entry ends up in the shared page cache and is served to everyone else.
  Empty states travel in the context and render `soccertime/empty_state.html`.
- The API's documentation page cannot be drf-spectacular's own: it pulls Swagger UI from a
  CDN and initialises it from an inline `<script>`, and `script-src` here is `self` with no
  nonce. `templates/soccertime/api_docs.html` serves the sidecar assets from this origin and
  passes the schema URL through a data attribute that `api_docs.js` reads.
- `SCHEMA_PATH_PREFIX_INSERT` is fed from `FORCE_SCRIPT_NAME`. Without it every path in the
  schema would be one production does not answer — and it is invisible locally, where the
  prefix is empty.
- The database keeps a **write-ahead log**, so it is two files: the newest commits sit in
  `db.sqlite3-wal` until a checkpoint. Never move or replace it with `cp` — take it through
  a connection with `python -m soccertime.backups snapshot-db`, and when replacing one,
  stop the service and delete the `-wal` and `-shm` beside it first. SQLite reads a leftover
  log as belonging to whatever file it finds, which is corruption rather than staleness.
- `Event.Meta.ordering` is deliberately the bare `date`. Ordering by related fields makes
  every count, lookup and admin query join those tables. Listings opt in with
  `EventQuerySet.chronological()`.

## Production operations

Every production operation belongs in the `Makefile`, never in an ad-hoc SSH command, so
it is reviewable and repeatable. `deploy-production` snapshots the database before
migrating. `.env.production` is not versioned — it holds the secret key — but the deploy
uploads it from the working copy, so production configuration changes take effect there.

The deploy no longer sends code. CI builds the image and publishes it to
`ghcr.io/tvalverde/soccertime:sha-<commit>`; `deploy-production` pulls that tag and retags it
to `soccertime:latest`, which is the name the compose file, the relay, the backups and the
prune all use — the registry is transport, not a new contract. Two consequences worth
remembering: **a commit that is not pushed, or whose checks have not passed, cannot be
deployed**, and the pull runs before anything on the server changes so that failure costs
nothing. Rolling back is either `soccertime:previous` on the host or
`make deploy-production DEPLOY_TAG=sha-<commit>` for anything CI ever published. Nothing
retags the pulled image but `remote_deploy`, which also drops the registry name — an image
still carrying one is not dangling, and `prune-remote-images` only reclaims dangling ones.

## Committing

Stage explicit paths. `git add -A` in this repository sweeps in sandbox artefacts that
are not real files.

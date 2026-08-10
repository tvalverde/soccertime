# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-08-10

A release dominated by a code review and the production work that came out of it: seven
confirmed bugs, two of them causing silent data loss, the transport security of a
publicly reachable admin, and a deploy that can no longer report success over a broken
site. The application code is now annotated and type-checked.

### Added
- Type annotations across the application code, checked by mypy with django-stubs through a new `make typecheck`, and ruff's ANN rules inside `make lint` so unannotated code cannot land. `mypy`, `django-stubs` and `types-requests` added to the requirements.
- `soccertime/rendering.py`, the single source of image markup for both the templates and the admin, exposed to templates as the `render_image_markup` filter. Models keep the image and its dimensions; the HTML lives outside them, so templates no longer need `|safe`. This finishes the decoupling the filter was introduced for.
- Test modules for `filters.py` and the template filters, which had none.
- `DJANGO_CACHE_LOCATION` to configure the file cache path.
- `redownload_images` management command (with `--dry-run`) to restore flag images whose file is missing from storage, re-fetching them from the URL each `Flag` keeps in its `name`.
- Shared `_image_download` module so `scrapit` and `redownload_images` use one guarded implementation of the image download.
- `EventQuerySet.chronological()` for the listing order (start time, then sport order, then competition name), now that the model default no longer carries it.
- `empty_state()` view helper and `soccertime/empty_state.html`, replacing the messages-based empty notice.
- `image_width` / `image_height` on `Flag` and `crest_width` / `crest_height` on `Team`, recorded by `save_image` and backfilled for existing rows, so rendering never opens an image file to measure it.
- Transport security settings driven from the environment through a new `env_flag()` helper: `DJANGO_BEHIND_TLS_PROXY`, `DJANGO_SECURE_COOKIES`, `DJANGO_SECURE_SSL_REDIRECT`, `DJANGO_SECURE_HSTS_SECONDS`, `DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS` and `DJANGO_SECURE_HSTS_PRELOAD`.
- `backup-remote-media` Makefile target, run by `deploy-production`, keeping the snapshot on the host rather than inside the volume it protects.
- `soccertime/backups.py`, applying generational retention to the snapshots — the last 3, one per day for 7 days, one per month for 12 months — because a plain count measures history in deploys rather than in time: six deploys in one afternoon evicted a five-month-old restore point. Database snapshots are now taken through SQLite's backup API and gzipped, so they are both consistent and a third of the size.
- `pull-remote-backups` Makefile target, since the database, the media and every snapshot otherwise live on the same machine.
- Crest reporting in `redownload_images`: broken references are listed even though a `Team` stores no source URL and therefore cannot be re-fetched automatically.
- `remote-smoke-test` and `wait-remote-healthy` Makefile targets, run at the end of `deploy-production`, so a deploy that leaves the site broken fails instead of reporting success. Pages are fetched from outside the server, because an unhealthy container is dropped from the proxy's routing table while still answering 200 on localhost.
- Makefile targets for production operations: `backup-remote-db` (run automatically by `deploy-production` before migrating), `list-remote-backups`, `restore-remote-db`, `remote-check`, `remote-clear-cache` and `remote-redownload-images`.
- `CLAUDE.md`, pointing at `AGENTS.md` and recording the verification rules learned from two production incidents.
- `duration` field (`DurationField`) to `Event` model allowing custom event durations (defaults to 2 hours if not specified).
- `validate_channel_link` validator to `ChannelLink.link` supporting IPTV and P2P protocols (`acestream`, `sop`, `rtmp`, `m3u8`, `intent`, `http`, `https`).
- Expanded test suite with 18 unit tests covering custom event durations across midnight, P2P link validation, manager forwarding, and template tags.
- Scraper support for team-specific pages in the `futbolenlatv` source to capture extra events (e.g. friendlies) not listed in the general agenda.
- Auto-discovery mechanism in `scrapit` command to automatically extract and persist team slugs from `<a>` tags during standard scraping.
- `futbolenlatv_slug` field to the `Team` model to store the identifier used on the source website.
- `local_slug` and `visitor_slug` fields to `MatchDetails` to decouple slug extraction from database persistence.
- `importm3u` management command to import acestream links from M3U playlist files (e.g. `mundial.m3u`), with the source name derived from the file name stem and an optional `--source` override.
- `*.m3u` pattern to `.gitignore`, since M3U playlists are external data sources that must not be committed.
- Rule in `GEMINI.md` to officially assign complex bug investigations and UI error diagnosis to the Opus 4.6 Architect subagent.
- Visual highlight (orange/gold left border) to `agenda_item.html` for matches involving favorite teams.
- `is_favorite_cached` property on `Team`, and `is_favorite_event` on `Event`, overridden by `Match`.
- Database prefetching for favorite relationships in `EventQuerySet.with_related()` to prevent N+1 queries.
- Rule regarding regression testing for bug fixes in `AGENTS.md`.
- Competition/Events title header to `agenda.html` to improve context visibility when filtering.
- Language and localization rules to `AGENTS.md`.
- Isolated `.geminiignore` and `.claudeignore` to prevent context duplication between LLM CLIs.

### Changed
- `LinkSchemeFilter` resolves the distinct link schemes with a single database query instead of reading every row into Python, and returns them in a stable order; they came from a set, so the admin dropdown could be ordered differently in each process.
- The admin attaches its generated relation columns once at registration instead of rewriting them on the shared `ModelAdmin` instance on every request, and reads `field.choices` rather than the private `field._choices`.
- `event_type` is applied by `Event.save()` from an `EVENT_TYPE` declared on each subclass, and the constant `is_favorite_event` default moved to `Event`, replacing three near-identical overrides apiece.
- Views share `get_base_context(with_teams=...)` instead of asking for the favourite teams and popping them back out, and their imports moved to module scope.
- The import commands roll a dry run back with `transaction.set_rollback(True)` instead of raising `TransactionManagementError` at themselves; `self.warnings` is created by the base command that consumes it.
- The empty-state strings are named constants wrapped in `gettext_lazy`. They still render in Spanish, as the site does.
- Docstrings, comments and management-command output are in English, per the project convention. The web interface stays in Spanish; only the code artifacts and the CLI changed, along with the stat keys in the link importer.
- The `env` template filter only reads allowlisted variables. It reaches every template, so `{{ "DJANGO_SECRET_KEY"|env }}` would otherwise render the secret into a page.
- `scrapit` upserts every event type through one `upsert_event`, replacing the same get / realign / dedupe algorithm copy-pasted three times.
- With caching disabled the cache backend is now explicitly `DummyCache`. Django's default is a per-process `LocMemCache`, which made the `cache.clear()` in the management commands appear to work while clearing only that process.
- `Event.Meta.ordering` reduced to `["date"]`. Ordering by competition and sport joined both tables and cast the timestamp on every query, including counts, lookups and admin lists; `Event` queries went from 2 joins to 0 and `Match` from 3 to 1.
- `ChannelLink.link` is unique again, restoring the constraint lost in migration `0029` and making the `update_or_create` upsert in `import_entries` safe. Existing duplicates are merged into the oldest row, which inherits its sources, channels and `verified` flag.
- Empty-state notices travel in the view context instead of the `messages` framework, which also removes one `.exists()` query per view. `AGENTS.md` updated accordingly.
- Refactored `EventManager` to `EventQuerySet.as_manager()` in `soccertime/models.py`.
- Removed redundant `event_ptr` from `unique_together` constraints on child MTI models (`Match`, `Race`, `SimpleEvent`).
- Refactored `Favorite.__str__` to safely handle unassigned or missing team/competition relations.
- Massive performance optimization (75% execution time reduction) in `scrapit` command by using `.set()` for Many-To-Many channel assignments, avoiding thousands of individual SQLite commit transactions caused by `clear()` and `add()` loops.
- `make test` and `make test-cov` now exclude integration tests (`-m "not integration"`) so the suite runs fast and offline; added `make test-integration` for the tests that scrape real sources.
- Extracted the shared link-import pipeline (name normalization, quality extraction, fuzzy channel matching, persistence and stats) from `addlinksource` into `BaseLinkImportCommand` (`_link_import_base.py`) for reuse by `importm3u`.
- Increased the mobile tab bar breakpoint trigger from `sm` (576px) to `md` (768px) to prevent layout breakages on tablets and landscape phones, offering a better mobile-like experience on medium screens.
- Decoupled `GEMINI.md` from `AGENTS.md` and added specific multi-agent workflow rules.

### Removed
- `channel_matchers.py`: 320 lines imported by nothing, advertised by Django as a command it could not run.
- `Sport.competitions_with_events`, `Sport.competitions_without_events` and `Competition.is_favorite`: superseded or byte-identical duplicates, used by nothing but the tests that kept them alive.
- `render_image`, `flag_image` and `crest_image` from the models, along with the duplicated fallback SVG. The markup moved to `soccertime/rendering.py`.
- `migrate_crests` management command. A one-off path migration from early 2026 whose "missing or empty file" branch cleared the crest reference of any team whose file was absent, turning a dangling reference the scraper repairs by itself into permanent loss: 1357 teams lost their crest that way.
- Legacy and redundant template files: `events.html`, `match_item.html`, `simple_event_item.html`, and `event_header.html`.

### Fixed
- The scraping dataclasses declared every field optional though `parse_iter` only yields complete events, and `Event.details` was typed `EventDetails` while the code passes `MatchDetails` and `RaceDetails`, which do not inherit from it; it is now a declared union narrowed by the existing `isinstance` dispatch.
- `team_events` sorted opponents with `opponent_dates.get(team.id)`, which would have raised `TypeError` inside `sorted` had the lookup ever missed.
- The link importer indexed `channel_link.link`, a nullable field, when reporting a duplicate.
- The channels page orders the links inside each card the same way the rest of the site does. It sorted only by the grouping keys, so the rows of a single card — which share all three — came back in whatever order the database chose, and the same play buttons appeared in one order there and another in the agenda. `CHANNEL_LINK_ORDERING` is now the single definition, used by the model and by the view.
- `upload-only` now extracts the uploaded archive. It left it packed, so a following `remote-restart` rebuilt the image from the previous version while reporting success.
- Deleting a `ChannelLinkSource` no longer destroys every source-less `ChannelLink`, including links created by hand in the admin. Only the links that belonged to the deleted source are considered.
- Detaching a link from the source side (`source.links.remove(...)`, as the admin form does) no longer raises `AttributeError`; the `m2m_changed` receiver honours `reverse` and `pk_set`.
- `/agenda/?events-date=<garbage>` returns the default agenda instead of HTTP 500.
- `EventQuerySet.favorites()` no longer duplicates an event when a team is listed in several `Favorite` rows.
- Scraping no longer aborts when a crest URL is missing or unreachable; failures are reported and skipped.
- `render_image` no longer opens each image file to measure it, cutting a 40-image page from 13.53 ms to 1.68 ms.
- Loading a row whose image file is missing no longer raises `FileNotFoundError`. Declaring `width_field` hooked Django's `update_dimension_fields` to `post_init`, which took `/competitions/` down with a 500 in production.
- The container health check is exempt from `SECURE_SSL_REDIRECT`. It reaches the app over plain HTTP, and a 301 made it fail, marking the container unhealthy and withdrawing it from the proxy, which returned 404 for every page.
- `BACKUP_SUFFIX` in the Makefile is an immediate assignment; as a recursive variable it re-ran `date` on every expansion and could name a different file than the one it created.
- Fixed `attempt to write a readonly database` in production management commands: remote SSH targets in the `Makefile` (`remote_deploy`, `upload-db`, `upload-requests-cache`, `upload-media`) hardcoded the local host UID (`DOCKER_UID`), which did not match the production container's `appuser` (UID 1000, owner of the data volumes). Introduced dedicated `REMOTE_DOCKER_UID`/`REMOTE_DOCKER_GID` variables (default 1000) for remote targets, decoupling them from the local `DOCKER_UID`.
- Fixed over-broad token fallback in the channel matcher (`BaseLinkImportCommand.match_channels`): short tokens ("5", "mx") were dropped, letting a generic token like "canal" associate a link (e.g. "CANAL 5 MX") to every unrelated "Canal *" channel. Short tokens are now required with word-boundary matching.
- Marked `test_dry_run_does_not_save` with the `integration` marker since it scrapes the real futbolenlatv source; the full non-integration suite no longer performs network requests.
- Fixed global N+1 query issue in `base.html` by adding `.select_related("flag")` to `get_favorite_competitions()` context processor.
- Fixed N+1 query issue in Django Admin's `EventModelAdmin` by prefetching channels for the `channels_names` column.
- Fixed severe N+1 query overhead in properties `is_favorite`, `has_events`, and `events_count` of `Competition` by refactoring them to use Python list comprehensions, enabling them to leverage the `prefetch_related` cache instead of hitting the database repeatedly.
- Fixed performance overhead in default `EventManager` by removing the implicit `with_related()` call, resolving massive `JOIN` drags on simple `.count()` and `.aggregate()` operations. Views now explicitly call `.with_related()`.
- Fixed performance bottleneck in `scrapit` command by introducing an in-memory local cache (`dict`) for `Team`, `Sport`, `Competition`, `Flag`, and `Channel` objects, drastically reducing `get_or_create` database operations during scraping loops.
- Fixed mobile layout for pagination overflowing the screen by wrapping elements in `agenda.html`.
- Fixed severe layout bug causing the `fixed-bottom` mobile navigation bar to overflow horizontally and detach vertically from the viewport by wrapping the `<table class="table">` in `agenda.html` with a `.table-responsive` container, preventing it from widening the body width.
- Fixed expandable teams bar not working on competition pages by moving the toggle script outside the favorites block in `base.html` and standardizing the UI component in `agenda.html`.
- `/healthz/` endpoint for Docker healthchecks, independent of the application cache.
- Intermittent 404 on `/soccertime/favorites/`: replaced per-site cache middleware (`UpdateCacheMiddleware`/`FetchFromCacheMiddleware`) with per-view `@cache_page` decorators. The per-site middleware was caching responses from the Docker healthcheck (which bypasses Traefik's `StripPrefix`), polluting the cache with entries keyed under inconsistent `SCRIPT_NAME` contexts. Per-view caching gives granular control and prevents the healthcheck from contaminating the cache.
- `Event.child_event` property to handle polymorphic event types (`Match`, `Race`, `SimpleEvent`) cleanly in templates.
- ARIA labels to all interactive elements and links for better accessibility.
- Flags to competitions in the favorites bar for visual consistency.
- F1 multi-session scraping: all sessions of the same Grand Prix weekend (Libres, Clasificación al Sprint, Sprint, Clasificación, Carrera) are now stored as independent `Race` records. Previously, all sessions shared the same race name and fell within the ±2-day deduplication window, causing `MultipleObjectsReturned` which deleted all but the most recent record, keeping only the Sunday race.
- Idempotency in `scrapit` command: `Race` and `SimpleEvent` deduplication now includes `details` (session type) as part of the lookup key, so only the datetime shifts within the same session type trigger an update.
- Removed hardcoded empty state alerts in favor of the global Django messages system.
- Deployment building unrelated images: `remote_deploy` and `remote-restart` now explicitly target the `soccertime-web` service.
- PermissionError during `collectstatic` in production: added a step to `chown` the static volume to the application user before running management commands.
- Horizontal scroll issue on Fire TV Silk: removed `text-nowrap` from table cells and reverted quick-access bars to show only crests to save horizontal space.
- PermissionError ("Operation not permitted") when downloading the database, requests cache, or media via `Makefile` by correctly setting file ownership on the remote host.
- `sqlite3.OperationalError` during `scrapit` in production: moved `requests_cache.install_cache()` out of module-level code into `_configure_cache()`, called lazily from `get_events()`. Added `os.makedirs(..., exist_ok=True)` to guarantee the cache directory exists before SQLite tries to open it. Also removed the spurious `.sqlite` extension from `REQUESTS_CACHE` in the Dockerfile (the library appends it automatically).

### Security
- Session and CSRF cookies are marked `Secure` in production, where the admin is publicly reachable and they previously travelled without the flag.
- HSTS enabled with a one-year lifetime, after confirming the public pages serve no `http://` resources. `includeSubDomains` and `preload` stay off deliberately, and their checks are silenced with that rationale so `check --deploy` stays a useful signal.
- `SECURE_SSL_REDIRECT` and `SECURE_PROXY_SSL_HEADER` enabled in production, so Django both recognises proxied HTTPS and redirects plain HTTP itself.

## [0.1.0] - 2026-03-08

### Added
- `DOCKER_UID` and `DOCKER_GID` variables with fallbacks (1000:1000) to `Makefile` for consistent user mapping across development and deployment.

### Fixed
- Permission issues in `upload-db`, `upload-requests-cache`, and `upload-media` targets by adding `chown` commands. This ensures that files uploaded to Docker volumes are owned by the application user instead of `root`.

### Security
- Explicitly set the `-u` flag in all `docker compose exec` commands within the `Makefile` (both local and remote) to strictly enforce the `appuser` (1000:1000) context.

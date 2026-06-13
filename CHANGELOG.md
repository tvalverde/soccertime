# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Visual highlight (orange/gold left border) to `agenda_item.html` for matches involving favorite teams.
- `is_favorite_cached` property to `Team` and `Competition` models, and `is_favorite_event` to `Event` subclasses.
- Database prefetching for favorite relationships in `EventQuerySet.with_related()` to prevent N+1 queries.
- Rule regarding regression testing for bug fixes in `AGENTS.md`.
- Competition/Events title header to `agenda.html` to improve context visibility when filtering.
- Language and localization rules to `AGENTS.md`.
- Isolated `.geminiignore` and `.claudeignore` to prevent context duplication between LLM CLIs.

### Changed
- Decoupled `GEMINI.md` from `AGENTS.md` and added specific multi-agent workflow rules.

### Fixed
- Fixed mobile layout for pagination overflowing the screen by wrapping elements in `agenda.html`.
- Fixed expandable teams bar not working on competition pages by moving the toggle script outside the favorites block in `base.html` and standardizing the UI component in `agenda.html`.

- `/healthz/` endpoint for Docker healthchecks, independent of the application cache.

### Fixed
- Intermittent 404 on `/soccertime/favorites/`: replaced per-site cache middleware (`UpdateCacheMiddleware`/`FetchFromCacheMiddleware`) with per-view `@cache_page` decorators. The per-site middleware was caching responses from the Docker healthcheck (which bypasses Traefik's `StripPrefix`), polluting the cache with entries keyed under inconsistent `SCRIPT_NAME` contexts. Per-view caching gives granular control and prevents the healthcheck from contaminating the cache.

- `Event.child_event` property to handle polymorphic event types (`Match`, `Race`, `SimpleEvent`) cleanly in templates.
- ARIA labels to all interactive elements and links for better accessibility.
- Flags to competitions in the favorites bar for visual consistency.

### Fixed
- F1 multi-session scraping: all sessions of the same Grand Prix weekend (Libres, Clasificación al Sprint, Sprint, Clasificación, Carrera) are now stored as independent `Race` records. Previously, all sessions shared the same race name and fell within the ±2-day deduplication window, causing `MultipleObjectsReturned` which deleted all but the most recent record, keeping only the Sunday race.
- Idempotency in `scrapit` command: `Race` and `SimpleEvent` deduplication now includes `details` (session type) as part of the lookup key, so only the datetime shifts within the same session type trigger an update.
- Removed hardcoded empty state alerts in favor of the global Django messages system.
- Deployment building unrelated images: `remote_deploy` and `remote-restart` now explicitly target the `soccertime-web` service.
- PermissionError during `collectstatic` in production: added a step to `chown` the static volume to the application user before running management commands.
- Horizontal scroll issue on Fire TV Silk: removed `text-nowrap` from table cells and reverted quick-access bars to show only crests to save horizontal space.
- PermissionError ("Operation not permitted") when downloading the database, requests cache, or media via `Makefile` by correctly setting file ownership on the remote host.
- `sqlite3.OperationalError` during `scrapit` in production: moved `requests_cache.install_cache()` out of module-level code into `_configure_cache()`, called lazily from `get_events()`. Added `os.makedirs(..., exist_ok=True)` to guarantee the cache directory exists before SQLite tries to open it. Also removed the spurious `.sqlite` extension from `REQUESTS_CACHE` in the Dockerfile (the library appends it automatically).

### Removed
- Legacy and redundant template files: `events.html`, `match_item.html`, `simple_event_item.html`, and `event_header.html`.

## [0.1.0] - 2026-03-08

### Added
- `DOCKER_UID` and `DOCKER_GID` variables with fallbacks (1000:1000) to `Makefile` for consistent user mapping across development and deployment.

### Fixed
- Permission issues in `upload-db`, `upload-requests-cache`, and `upload-media` targets by adding `chown` commands. This ensures that files uploaded to Docker volumes are owned by the application user instead of `root`.

### Security
- Explicitly set the `-u` flag in all `docker compose exec` commands within the `Makefile` (both local and remote) to strictly enforce the `appuser` (1000:1000) context.

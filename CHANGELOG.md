# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `Event.child_event` property to handle polymorphic event types (`Match`, `Race`, `SimpleEvent`) cleanly in templates.
- ARIA labels to all interactive elements and links for better accessibility.
- Flags to competitions in the favorites bar for visual consistency.

### Fixed
- Idempotency in `scrapit` command: existing `Race` and `SimpleEvent` records are now updated instead of duplicated when details or dates change slightly.
- Removed hardcoded empty state alerts in favor of the global Django messages system.
- Deployment building unrelated images: `remote_deploy` and `remote-restart` now explicitly target the `soccertime-web` service.
- PermissionError during `collectstatic` in production: added a step to `chown` the static volume to the application user before running management commands.
- Horizontal scroll issue on Fire TV Silk: removed `text-nowrap` from table cells and reverted quick-access bars to show only crests to save horizontal space.

### Changed
- Unified all event listing views (`sport_events`, `channel_events`, `competition_events`) to use `agenda.html`, ensuring a consistent dark-themed UI.
- Optimized `competitions` and `team_events` views to eliminate N+1 query bottlenecks.
- Optimized channel link rendering using nested prefetching and template-level caching (`{% with %}`).
- Refactored `Channel.enabled_links` to use in-memory filtering, leveraging Django's prefetch cache.

### Fixed
- Idempotency in `scrapit` command: existing `Race` and `SimpleEvent` records are now updated instead of duplicated when details or dates change slightly.
- Removed hardcoded empty state alerts in favor of the global Django messages system.

### Removed
- Legacy and redundant template files: `events.html`, `match_item.html`, `simple_event_item.html`, and `event_header.html`.

## [0.1.0] - 2026-03-08

### Added
- `DOCKER_UID` and `DOCKER_GID` variables with fallbacks (1000:1000) to `Makefile` for consistent user mapping across development and deployment.

### Fixed
- Permission issues in `upload-db`, `upload-requests-cache`, and `upload-media` targets by adding `chown` commands. This ensures that files uploaded to Docker volumes are owned by the application user instead of `root`.

### Security
- Explicitly set the `-u` flag in all `docker compose exec` commands within the `Makefile` (both local and remote) to strictly enforce the `appuser` (1000:1000) context.

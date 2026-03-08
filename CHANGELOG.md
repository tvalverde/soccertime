# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-03-08

### Added
- `DOCKER_UID` and `DOCKER_GID` variables with fallbacks (1000:1000) to `Makefile` for consistent user mapping across development and deployment.

### Fixed
- Permission issues in `upload-db`, `upload-requests-cache`, and `upload-media` targets by adding `chown` commands. This ensures that files uploaded to Docker volumes are owned by the application user instead of `root`.

### Security
- Explicitly set the `-u` flag in all `docker compose exec` commands within the `Makefile` (both local and remote) to strictly enforce the `appuser` (1000:1000) context.

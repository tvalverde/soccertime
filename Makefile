.PHONY: check-gradle-home help typecheck screenshot prune-images remote-apply-config remote-admin-on remote-admin-off remote-admin-set deploy-production pull_image remote_deploy upload-compose upload-config remote-restart remote-scrape purge-old-events remote-purge-old-events replica-up replica-up-published replica-build replica-pull replica-serve replica-manage replica-migrate replica-relay remote-check remote-ps remote-pull remote-logs remote-error-check remote-smoke-test wait-remote-healthy remote-clear-cache remote-redownload-images remote-import-links remote-install-import-cron remote-install-logrotate prune-remote-images prune-remote-app-path backup-remote-db backup-remote-media prune-remote-backups pull-remote-backups list-remote-backups restore-remote-db download-db upload-db download-requests-cache upload-requests-cache download-media upload-media test test-integration test-cov lint lint-fix format android-build android-test android-lint android-clean android-release android-install-mobile android-install-tv

# Default target: show help
.DEFAULT_GOAL := help

# Show help with all available commands
help:
	@echo "Soccertime - Deployment and management commands"
	@echo ""
	@echo "USAGE: make <target>"
	@echo ""
	@echo "DEVELOPMENT:"
	@echo "  test                 Run tests (excludes integration tests)"
	@echo "  test-integration     Run integration tests (real HTTP requests)"
	@echo "  test-cov             Run tests with coverage report"
	@echo "  lint                 Check code for linting errors"
	@echo "  typecheck            Check type annotations with mypy"
	@echo "  screenshot           Capture a page headlessly, firefox then chrome (URL=, OUT=, SIZE=)"
	@echo "  lint-fix             Fix auto-fixable linting errors"
	@echo "  prune-images         Drop this project's superseded images from this machine"
	@echo "  format               Format code with ruff"
	@echo ""
	@echo "ANDROID (host toolchain: JDK + Android SDK, not the container):"
	@echo "  android-build        Assemble both debug APKs"
	@echo "  android-test         Run the JVM unit tests"
	@echo "  android-lint         Run Android Lint on every module"
	@echo "  android-clean        Drop the Gradle build output"
	@echo "  android-release      Assemble the signed release APKs (needs the keystore)"
	@echo "  android-install-mobile  Install the phone app on the attached device"
	@echo "  android-install-tv   Install the TV app over the network (ADB_HOST=192.168.1.42)"
	@echo ""
	@echo "DEPLOY:"
	@echo "  deploy-production    Full deploy (pull the published image and hand over)"
	@echo "  upload-config        Upload only .env.production"
	@echo "  upload-compose       Upload the service definition of the deployed commit"
	@echo "  remote-restart       Recreate remote services via orchestrator"
	@echo "  remote-scrape        Run the scraper on the remote server and clear cache"
	@echo "  remote-install-import-cron  Install the periodic link import (SOURCE=, URL=)"
	@echo "  remote-install-logrotate    Rotate the logs those cron entries write"
	@echo "  remote-check         Run Django's deployment checks on production"
	@echo "  remote-pull          Refresh remote images, skipping the ones built on the host"
	@echo "  remote-logs          Read the application log (SINCE=10m, GREP=\" 500 \", TAIL=200)"
	@echo "  replica-up           Start the local production replica, ready to serve"
	@echo "  replica-up-published Same, on the image CI published for this commit"
	@echo "  replica-migrate      Migrate the local production replica as its database owner"
	@echo "  replica-relay        Rehearse the deploy handover against the replica"
	@echo "  remote-smoke-test    Verify a live deploy from outside (health + public pages)"
	@echo "  remote-clear-cache   Drop the rendered page cache on production"
	@echo "  remote-redownload-images  Restore flag images missing from the media volume"
	@echo "  remote-import-links  Import channel links (SOURCE=, FILE=, ARGS=--dry)"
	@echo "  prune-remote-images  Drop this project's superseded images, keeping :previous"
	@echo "  prune-remote-app-path Drop the code left on the server by the old deploy"
	@echo "  remote-apply-config  Upload .env.production and recreate the container"
	@echo "  remote-admin-on      Expose the admin on production (remember to turn it off)"
	@echo "  remote-admin-off     Remove the admin from production's URLs entirely"
	@echo ""
	@echo "DATABASE (SQLite in Docker volume):"
	@echo "  backup-remote-db     Snapshot the database to the host, compressed (~5.5 MB)"
	@echo "  backup-remote-media  Snapshot the media volume to the host (~2 MB)"
	@echo "  pull-remote-backups  Copy the remote snapshots to $(LOCAL_BACKUP_PATH)"
	@echo "  list-remote-backups  List the snapshots kept on the remote host"
	@echo "  restore-remote-db    Restore a snapshot (BACKUP=<file>) and restart the service"
	@echo "  download-db          Download database from remote volume"
	@echo "  upload-db            Upload database to remote volume"
	@echo ""
	@echo "REQUESTS CACHE (in DB volume):"
	@echo "  download-requests-cache  Download requests cache from remote volume"
	@echo "  upload-requests-cache    Upload requests cache to remote volume"
	@echo ""
	@echo "MEDIA (Docker volume):"
	@echo "  download-media       Download media from remote volume"
	@echo "  upload-media         Upload media to remote volume"
	@echo ""
	@echo "NOTE: Uploads/downloads create timestamped backups where applicable."

# Deployment configuration variables
# Loaded from .env file if available
-include .env
export

DOCKER_UID ?= 1000
DOCKER_GID ?= 1000

# UID/GID of the appuser inside the production image. This is decoupled from
# DOCKER_UID (the local host user) because remote SSH targets run against the
# production container, whose appuser and data volumes are owned by this UID.
REMOTE_DOCKER_UID ?= 1000
REMOTE_DOCKER_GID ?= 1000

APP_NAME = soccertime

# Remote paths
REMOTE_APP_PATH ?= ~/www/soccertime
REMOTE_DOCKER_PATH ?= ~/docker
REMOTE_DOCKER_COMPOSE_FILE ?= docker-compose.yml
REMOTE_SOCCERTIME_SERVICE ?= soccertime-web

# Production Docker volumes
REMOTE_DB_VOLUME ?= docker_soccertime-db
REMOTE_MEDIA_VOLUME ?= docker_soccertime-media
REMOTE_STATIC_VOLUME ?= docker_soccertime-static

# Paths inside helper containers
REMOTE_DB_FILE_IN_VOLUME ?= db.sqlite3
REMOTE_CACHE_FILE_IN_VOLUME ?= soccertime_data_cache.sqlite

# Public entry point and pages checked after a deploy. Override in .env if they change.
# The API listing and its documentation page are in here because they are the only things
# that would notice a production image built without the new dependencies: `/healthz/`
# renders no template and answers green either way, which is exactly how a deploy reported
# success while every page returned 500. The smoke test appends `?smoke=<pid>`, which the
# API ignores by design — an unknown parameter must never turn a listing into a 400.
PRODUCTION_URL ?= https://www.mojon.es/soccertime
SMOKE_PATHS ?= /healthz/ /favorites/ /agenda/ /competitions/ /channels/ /api/v1/events/ /api/v1/docs/

# Defaults for `remote-logs`. `SINCE` accepts anything `docker compose logs --since` does,
# so `10m`, `1h` or an ISO timestamp. `GREP` is a plain pattern, empty for everything.
LOG_TAIL ?= 200
LOG_SINCE ?=
LOG_GREP ?=

# The status codes `remote-error-check` treats as a failed release. A variable so the check
# itself can be exercised — pointing it at 2xx must find the traffic that is certainly there,
# which is the only way to know the pattern matches anything at all.
ERROR_STATUS ?= 5[0-9][0-9]
# Traefik 3 marks a newly discovered server DOWN until its first probe succeeds — v2 marked
# it up and found out later. So a container answering `/healthz/` is not yet receiving
# traffic, and retiring the old one at that moment leaves the service with no live server:
# 502, then 503, then the router is dropped altogether and every path answers 404. Measured
# at 13 seconds in production and 2.4 in the replica once its proxy was pinned to the same
# version. Five probe intervals is the margin that removed it.
PROXY_SETTLE_SECONDS ?= 5

HEALTH_TIMEOUT ?= 90

# Generational retention. A plain count measures history in deploys rather than in time:
# six deploys in one afternoon once evicted a five-month-old restore point, and the data
# problem it was needed for had gone unnoticed since March. Each tier keeps the newest
# snapshot of its period, so ~22 copies at ~7.5 MB each is the ceiling.
KEEP_LAST ?= 3
KEEP_DAILY ?= 7
KEEP_MONTHLY ?= 12

# Snapshots live on the host, not inside the volumes they protect: losing a volume is the
# failure they guard against, and it would take the backup with it.
REMOTE_BACKUP_PATH ?= ~/soccertime-backups
# Bind-mounted into the container, unlike /tmp which is a tmpfs there.
REMOTE_SHARED_PATH ?= ~/shared

# Every six hours, an hour after the scraper's 4-hourly entry rather than alongside it.
CRON_SCHEDULE ?= 20 1,7,13,19 * * *
IMPORT_CRON_COMMAND = docker compose -f ./docker/$(REMOTE_DOCKER_COMPOSE_FILE) exec --user appuser $(REMOTE_SOCCERTIME_SERVICE) python manage.py addlinksource --source=$(SOURCE) --url=$(URL) >> ~/addlinksource-$(SOURCE).log 2>&1
LOGROTATE_CRON_COMMAND = /usr/sbin/logrotate --state ~/logrotate/soccertime.state ~/logrotate/soccertime.conf >> ~/logrotate/soccertime.log 2>&1
CONTAINER_SHARED_PATH ?= /shared
LOCAL_BACKUP_PATH ?= ./backups
REMOTE_IMAGE ?= $(APP_NAME):latest
BACKUP_TIMESTAMP := $(shell date +%Y%m%d_%H%M%S)

# === Development Commands ===

# Run tests
test:
	@docker compose exec -u $(DOCKER_UID):$(DOCKER_GID) web pytest -m "not integration"

# Run integration tests (may make real HTTP requests)
test-integration:
	@docker compose exec -u $(DOCKER_UID):$(DOCKER_GID) web pytest -m integration

# Run tests with coverage report
test-cov:
	@docker compose exec -u $(DOCKER_UID):$(DOCKER_GID) web pytest -m "not integration" --cov --cov-report=term-missing

# === Android Commands ===
#
# The apps under `android/` build with their own toolchain and share nothing with the Django
# container: Gradle runs on the host, against a JDK and an Android SDK it expects to find
# there. These targets exist for the same reason the deploy ones do — so the command that was
# run is written down rather than remembered.
#
# Sideloading is not a convenience. The three things that decide whether these apps work at
# all — the TLS handshake on Android 7.1, whether anything answers an `acestream://` intent,
# and whether every control can be reached with a D-pad — are invisible to an emulator and to
# the unit suite, and `android-install-tv` is how they get in front of the real hardware.
ANDROID_DIR := android
GRADLEW := ./gradlew
ADB ?= adb
ADB_PORT ?= 5555

# Gradle's cache is the user's, at `~/.gradle`, and these targets deliberately leave it
# there: it is three gigabytes of dependencies that every project on the machine already
# shares, and a build resolving its own copy is a build resolving a different tree from the
# one the developer sees. That divergence is slow to diagnose and easy to prevent.
#
# The guard exists because it was not prevented. A tool sandbox once refused a write to
# `~/.gradle`, the answer was to point `GRADLE_USER_HOME` at a temporary directory, and that
# answer outlived its reason — every later build re-downloaded a gigabyte and a half and ran
# a second daemon beside the one already warm. The right answer to a sandbox refusing
# `~/.gradle` is to let the build out of the sandbox, not to move the cache.
check-gradle-home:
	@if [ -n "$$GRADLE_USER_HOME" ] && [ "$${GRADLE_USER_HOME#$$HOME}" = "$$GRADLE_USER_HOME" ]; then \
		echo "GRADLE_USER_HOME points outside your home:"; \
		echo "    $$GRADLE_USER_HOME"; \
		echo ""; \
		echo "These targets build against ~/.gradle on purpose. A cache somewhere else"; \
		echo "re-downloads what you already have and resolves its own dependency tree."; \
		echo "Unset it, or pass a path under \$$HOME if you meant it."; \
		exit 1; \
	fi

android-build: check-gradle-home
	@cd $(ANDROID_DIR) && $(GRADLEW) assembleDebug

android-test: check-gradle-home
	@cd $(ANDROID_DIR) && $(GRADLEW) testDebugUnitTest

android-lint: check-gradle-home
	@cd $(ANDROID_DIR) && $(GRADLEW) lint

android-clean: check-gradle-home
	@cd $(ANDROID_DIR) && $(GRADLEW) clean

# Signed, and therefore only from a machine holding the keystore. CI does this from a secret
# on an `android-v*` tag; this is the rehearsal of that, not a second way to release.
android-release: check-gradle-home
	@cd $(ANDROID_DIR) && $(GRADLEW) assembleRelease

# Gradle's installDebug installs on EVERY adb device connected at that moment — measured on
# 2026-08-30, when it put the phone app on both Fire TVs that had stayed connected. With more
# than one device attached this refuses to guess; pin the phone with its serial from
# `adb devices`: make android-install-mobile ANDROID_SERIAL=<serial>.
android-install-mobile:
	@if [ -z "$(ANDROID_SERIAL)" ] && [ "$$($(ADB) devices | awk 'NR>1 && $$2=="device"' | wc -l)" -gt 1 ]; then \
		echo "More than one adb device is connected and installDebug would install on ALL of them."; \
		echo "Usage: make android-install-mobile ANDROID_SERIAL=<serial from 'adb devices'>"; \
		exit 1; \
	fi
	@cd $(ANDROID_DIR) && $(if $(ANDROID_SERIAL),ANDROID_SERIAL=$(ANDROID_SERIAL)) $(GRADLEW) :app-mobile:installDebug

# The Fire TV has no USB port to plug into, so it is reached over the network: enable ADB
# debugging in Developer options, read the address from Settings, and pass it here.
# Usage: make android-install-tv ADB_HOST=192.168.1.42
android-install-tv:
	@if [ -z "$(ADB_HOST)" ]; then \
		echo "Usage: make android-install-tv ADB_HOST=<the Fire TV's address>"; \
		echo "  Enable it first in Settings > My Fire TV > Developer options > ADB debugging."; \
		exit 1; \
	fi
	@$(ADB) connect $(ADB_HOST):$(ADB_PORT)
	@cd $(ANDROID_DIR) && ANDROID_SERIAL=$(ADB_HOST):$(ADB_PORT) $(GRADLEW) :app-tv:installDebug
	@echo "Installed. Read what it does with: $(ADB) -s $(ADB_HOST):$(ADB_PORT) logcat -s Soccertime:V"

# Capture a page for visual review, with no browser extension involved.
# Firefox goes first, but on a desktop with Firefox already open it often hands the URL
# to the running instance and captures nothing, exiting successfully all the same. So the
# result is checked rather than assumed, and Chrome finishes the job when that happens.
# Usage: make screenshot URL=http://localhost:8000/agenda/ [OUT=shot.png] [SIZE=1280,900]
SCREENSHOT_SIZE ?= 1280,900
SCREENSHOT_OUT ?= screenshot.png

screenshot:
	@if [ -z "$(URL)" ]; then \
		echo "Usage: make screenshot URL=<url> [OUT=shot.png] [SIZE=1280,900]"; \
		exit 1; \
	fi
	@code=$$(curl -s -o /dev/null -w "%{http_code}" -L "$(URL)"); \
	case "$$code" in 2*|3*) ;; *) echo "Warning: $(URL) answered $$code; the capture will show the browser's error page" ;; esac
	@out="$(if $(OUT),$(OUT),$(SCREENSHOT_OUT))"; \
	size="$(if $(SIZE),$(SIZE),$(SCREENSHOT_SIZE))"; \
	rm -f "$$out"; \
	profile=$$(mktemp -d); \
	MOZ_NO_REMOTE=1 firefox --new-instance --headless --profile "$$profile" \
		--window-size=$$size --screenshot "$$out" "$(URL)" >/dev/null 2>&1 || true; \
	rm -rf "$$profile"; \
	if [ -s "$$out" ]; then \
		echo "Written by firefox: $$out"; \
	else \
		google-chrome --headless --disable-gpu --hide-scrollbars \
			--window-size=$$size --screenshot="$$out" "$(URL)" >/dev/null 2>&1 || true; \
		if [ -s "$$out" ]; then \
			echo "Written by chrome, firefox produced nothing: $$out"; \
		else \
			echo "Neither firefox nor chrome produced a screenshot of $(URL)"; \
			exit 1; \
		fi; \
	fi

# Check type annotations. Runs in the container because the django-stubs plugin imports
# the settings module, which needs the environment the container already provides.
typecheck:
	@docker compose exec -u $(DOCKER_UID):$(DOCKER_GID) web mypy soccertime/

# Check code for linting errors
lint:
	@docker compose exec -u $(DOCKER_UID):$(DOCKER_GID) web ruff check soccertime/

# Fix auto-fixable linting errors
lint-fix:
	@docker compose exec -u $(DOCKER_UID):$(DOCKER_GID) web ruff check soccertime/ --fix

# Format code with ruff
format:
	@docker compose exec -u $(DOCKER_UID):$(DOCKER_GID) web ruff format soccertime/

# === Deployment Commands ===

# Configuration files to upload. Both describe how to run the image on this server, which is
# the one thing the image itself cannot carry: the environment file holds the secret key and
# is deliberately not in the repository, and the compose file is what the server's own
# `~/docker/docker-compose.yml` includes from the uploaded directory rather than defining
# itself. That include is why the compose file has to keep travelling now that the archive
# does not — a definition left behind would go on being used, with nothing to say it is old.
ENV_PROD_FILE = .env.production
COMPOSE_PROD_FILE = compose.production.yaml

# The published image, and the tag of the commit being deployed. CI tags with the full hash
# — `type=sha,format=long` — which is what `git rev-parse` prints, so the two agree by
# construction rather than by convention; `test_deploy_transport.py` holds them together.
#
# Overriding DEPLOY_TAG is the rollback that does not depend on the server still holding
# `:previous`, and it can reach any commit CI ever published:
#
#   make deploy-production DEPLOY_TAG=sha-<commit>
GHCR_IMAGE ?= ghcr.io/tvalverde/soccertime
DEPLOY_TAG ?= sha-$(shell git rev-parse HEAD)
# The same commit without the tag's prefix. The compose file the server runs is read out of
# git at this revision, so overriding DEPLOY_TAG moves the definition with the image rather
# than pairing an old image with today's working copy.
DEPLOY_COMMIT = $(DEPLOY_TAG:sha-%=%)

# Main target for production deployment.
# The pull comes first: it is the step most likely to fail — the commit may not be published
# yet, or CI may still be running — and failing it after the database has been snapshotted
# and the configuration uploaded would leave work half done for nothing.
# The snapshots run before remote_deploy, which is what applies the migrations,
# and the smoke test runs last so a deploy that leaves the site broken fails loudly.
deploy-production: pull_image upload-compose upload-config backup-remote-db backup-remote-media remote_deploy remote-smoke-test prune-remote-images
	@echo "Deployment process completed successfully."

# Fetch the image CI built for this commit. Nothing on the server has changed when this runs,
# so a commit that was never published, or whose checks failed, costs a message and no state.
pull_image:
	@echo "--- Pulling $(GHCR_IMAGE):$(DEPLOY_TAG) ---"
	@ssh -p$(REMOTE_PORT) $(REMOTE_HOST) 'docker pull $(GHCR_IMAGE):$(DEPLOY_TAG)' || { \
		echo ""; \
		echo "The pull did not happen. Read the error above before assuming which:"; \
		echo "  a 'not found' means no image was published for this commit — it has to be"; \
		echo "  pushed and its checks green ('gh run watch'), or name one that exists with"; \
		echo "  'make deploy-production DEPLOY_TAG=sha-<commit>'. Anything else — a refused"; \
		echo "  connection, a name that does not resolve — is the server, not the image."; \
		exit 1; \
	}

# Target to execute deployment commands on remote server via SSH
#
# The configuration check and `collectstatic` both run in a throwaway container before the
# application is recreated. The check is what catches a security setting that quietly went
# missing from `.env.production` — dropped HSTS, a lost `SECURE_SSL_REDIRECT`, a cookie no
# longer marked secure — none of which the image can defend against with a baked default,
# because the right value depends on where it is deployed. Run after `up -d` it would only
# report the problem with the bad container already serving; run here it fails the deploy
# while the previous one is still up. `--fail-level WARNING` is what makes it a gate: those
# checks are warnings, and the two this project has decided against are silenced in
# `SILENCED_SYSTEM_CHECKS` rather than ignored here.
#
# `collectstatic` runs there too, not
# Migrations run BEFORE the handover, in a throwaway container running the new code, while
# the previous container is still serving. The old code must therefore tolerate the migrated
# schema — which additive migrations satisfy by construction, since Django only selects the
# columns a model declares. The order used to be the reverse, and the day a migration added
# columns the new code reads, every page the new container served before `migrate` finished
# would have answered 500 — caught by the deploy's own error gate, but caught is not avoided.
# The discipline this buys: destructive migrations need a two-release path (stop reading
# first, drop later), which is the standard additive-first rule.
# through `exec` afterwards. Static filenames carry a content hash, and the manifest that
# maps plain names to hashed ones is read once, the first time a template renders a
# `{% static %}` tag. Collecting afterwards meant the new process could read a manifest
# that was still missing or half-written and then hold it for its whole life: every page
# answered 500 while `/healthz/` — which renders no template — stayed green, so the
# container looked healthy with the site down. Finishing the collection first removes the
# window rather than papering over it with a second restart.
#
# The image itself is not built here any more: `pull_image` has already fetched the one CI
# built for this commit, and this retags it to the name everything on the host uses. The
# registry name is then dropped — an image still carrying one is not dangling, and
# `prune-remote-images` reclaims superseded images by pruning the dangling ones, so leaving
# the tag behind would turn that prune into a no-op and fill the disk over releases.
remote_deploy:
	@echo "--- Initiating remote deployment via SSH ---"
	ssh -p$(REMOTE_PORT) $(REMOTE_HOST) ' \
		set -e && \
		cd $(REMOTE_DOCKER_PATH) && \
		{ docker image inspect $(APP_NAME):latest >/dev/null 2>&1 \
			&& docker tag $(APP_NAME):latest $(APP_NAME):previous || true; } && \
		echo "--- Putting the pulled image under the name the host runs ---" && \
		docker tag $(GHCR_IMAGE):$(DEPLOY_TAG) $(APP_NAME):latest && \
		docker rmi $(GHCR_IMAGE):$(DEPLOY_TAG) && \
		echo "--- Fixing static volume permissions ---" && \
		docker run --rm -v $(REMOTE_STATIC_VOLUME):/data alpine chown -R $(REMOTE_DOCKER_UID):$(REMOTE_DOCKER_GID) /data && \
		echo "--- Checking the configuration before anything runs on it ---" && \
		docker compose -f $(REMOTE_DOCKER_COMPOSE_FILE) run --rm --no-deps \
			-u $(REMOTE_DOCKER_UID):$(REMOTE_DOCKER_GID) $(REMOTE_SOCCERTIME_SERVICE) \
			python manage.py check --deploy --fail-level WARNING && \
		echo "--- Collecting static files, before anything serves them ---" && \
		docker compose -f $(REMOTE_DOCKER_COMPOSE_FILE) run --rm --no-deps \
			-u $(REMOTE_DOCKER_UID):$(REMOTE_DOCKER_GID) $(REMOTE_SOCCERTIME_SERVICE) \
			python manage.py collectstatic --noinput && \
		echo "--- Applying database migrations, before the new code serves ---" && \
		docker compose -f $(REMOTE_DOCKER_COMPOSE_FILE) run --rm --no-deps \
			-u $(REMOTE_DOCKER_UID):$(REMOTE_DOCKER_GID) $(REMOTE_SOCCERTIME_SERVICE) \
			python manage.py migrate --noinput && \
		echo "--- Preparation done; the relay script takes it from here ---" \
	'
	@echo "--- Handing the service over to the new image ---"
	@ssh -p$(REMOTE_PORT) $(REMOTE_HOST) ' \
		cd $(REMOTE_DOCKER_PATH) && \
		COMPOSE_CMD="docker compose -f $(REMOTE_DOCKER_COMPOSE_FILE)" \
		HEALTH_TIMEOUT=$(HEALTH_TIMEOUT) PROXY_SETTLE_SECONDS=$(PROXY_SETTLE_SECONDS) \
		sh -s $(REMOTE_SOCCERTIME_SERVICE) $(APP_NAME):latest \
	' < scripts/relay.sh

# Target to upload the service definition the server includes, taken from git at the commit
# being deployed rather than from the working copy. The archive used to guarantee that by
# construction, being made from a commit; a plain `scp` would put a half-finished compose
# edit into production without passing through git or CI, and on a rollback it would pair an
# old image with today's definition — a combination nothing has ever run.
#
# Separate from `upload-config` because that one is also what `remote-apply-config` and the
# admin toggles run, and those have no business replacing the definition of a live service.
upload-compose:
	@echo "--- Uploading $(COMPOSE_PROD_FILE) as of $(DEPLOY_COMMIT) ---"
	@ssh -p$(REMOTE_PORT) $(REMOTE_HOST) 'mkdir -p $(REMOTE_APP_PATH)'
	@git show $(DEPLOY_COMMIT):$(COMPOSE_PROD_FILE) | \
		ssh -p$(REMOTE_PORT) $(REMOTE_HOST) 'cat > $(REMOTE_APP_PATH)/$(COMPOSE_PROD_FILE)'

# Target to upload only the configuration file (`.env.production`), which is not in the
# repository — it holds the secret key — so the local copy is the one of record, and it
# cannot be baked into a published image for the same reason.
upload-config:
	@echo "--- Uploading the environment the container reads ---"
	@ssh -p$(REMOTE_PORT) $(REMOTE_HOST) 'mkdir -p $(REMOTE_APP_PATH)'
	@if [ -f "$(ENV_PROD_FILE)" ]; then \
		echo "Uploading $(ENV_PROD_FILE)..."; \
		scp -P$(REMOTE_PORT) $(ENV_PROD_FILE) $(REMOTE_HOST):$(REMOTE_APP_PATH)/; \
		echo "Configuration uploaded successfully."; \
	else \
		echo "Warning: $(ENV_PROD_FILE) not found locally. Nothing uploaded."; \
	fi

# Target to recreate remote services without deploying. No `--build`: there is nothing on the
# server to build from, and the image under `soccertime:latest` is the one a deploy pulled.
remote-restart:
	@echo "--- Restarting remote services (safe up) ---"
	ssh -p$(REMOTE_PORT) $(REMOTE_HOST) ' \
		set -e; \
		cd $(REMOTE_DOCKER_PATH); \
		docker compose -f $(REMOTE_DOCKER_COMPOSE_FILE) up -d --remove-orphans $(REMOTE_SOCCERTIME_SERVICE); \
		echo "Services restarted successfully." \
	'

# Target to run the scraper on the remote production server and clear the cache
remote-scrape:
	@echo "--- Running remote scraper and clearing cache ---"
	ssh -p$(REMOTE_PORT) $(REMOTE_HOST) ' \
		set -e; \
		cd $(REMOTE_DOCKER_PATH); \
		echo "Running scraper..."; \
		docker compose -f $(REMOTE_DOCKER_COMPOSE_FILE) exec -u $(REMOTE_DOCKER_UID):$(REMOTE_DOCKER_GID) $(REMOTE_SOCCERTIME_SERVICE) python manage.py scrapit; \
		echo "Scrape done; the cache is cleared per container by the target below."; \
		echo "Remote scrape and cache clear completed successfully." \
	'
	@$(MAKE) --no-print-directory remote-clear-cache

# Target to purge historical events locally (default: 90 days)
# Usage: make purge-old-events [DAYS=90] [ARGS=--dry-run]
PURGE_DAYS ?= 90

purge-old-events:
	@echo "--- Purging historical events older than $(PURGE_DAYS) days ---"
	docker compose exec -u $(DOCKER_UID):$(DOCKER_GID) web python manage.py purge_old_events --days=$(PURGE_DAYS) $(ARGS)

# Target to purge historical events on the remote production server
# Usage: make remote-purge-old-events [DAYS=90] [ARGS=--dry-run]
remote-purge-old-events:
	@echo "--- Purging historical events on production older than $(PURGE_DAYS) days ---"
	ssh -p$(REMOTE_PORT) $(REMOTE_HOST) ' \
		set -e; \
		cd $(REMOTE_DOCKER_PATH); \
		docker compose -f $(REMOTE_DOCKER_COMPOSE_FILE) exec -u $(REMOTE_DOCKER_UID):$(REMOTE_DOCKER_GID) \
			$(REMOTE_SOCCERTIME_SERVICE) python manage.py purge_old_events --days=$(PURGE_DAYS) $(ARGS); \
	'

# === Data Management (Docker volumes in production) ===

LOCAL_DB_PATH = ./db/db.sqlite3
LOCAL_CACHE_PATH = ./soccertime_data_cache.sqlite
LOCAL_MEDIA_PATH = ./media
# Immediate assignment on purpose: a recursive one re-runs `date` on every expansion, so
# a recipe naming the backup twice could straddle a second and report the wrong file.
BACKUP_SUFFIX := .backup.$(shell date +%Y%m%d_%H%M%S)

# Snapshot the production database inside its own volume. Kept on the server so a bad
# Snapshot the database to the host, compressed and consistent. Copying the file byte by
# byte can capture a half-written transaction; the SQLite backup API cannot.
# The database volume is mounted writable, which a backup has no use for and SQLite
# insists on: reading a write-ahead-logged database means reading its log, and for that
# it must create the shared-memory index beside it — which a clean close deletes. On a
# read-only mount it cannot, and the snapshot dies with `unable to open database file`.
# That broke this target in production the day the log was enabled.
backup-remote-db:
	@echo "--- Backing up remote database ---"
	@ssh -p$(REMOTE_PORT) $(REMOTE_HOST) ' \
		set -e; \
		mkdir -p $(REMOTE_BACKUP_PATH); \
		docker run --rm -u $(REMOTE_DOCKER_UID):$(REMOTE_DOCKER_GID) \
			-v $(REMOTE_DB_VOLUME):/db -v $(REMOTE_BACKUP_PATH):/backups $(REMOTE_IMAGE) \
			python -m soccertime.backups snapshot-db /db/$(REMOTE_DB_FILE_IN_VOLUME) \
				/backups/db.$(BACKUP_TIMESTAMP).sqlite3.gz \
	'
	@$(MAKE) --no-print-directory prune-remote-backups

# Snapshot the media volume. Around 2 MB compressed, worth keeping even though most
# images can be re-fetched: a flag carries its source URL, but a team crest does not, so
# it only comes back if that team happens to play again.
backup-remote-media:
	@echo "--- Backing up remote media ---"
	@ssh -p$(REMOTE_PORT) $(REMOTE_HOST) ' \
		set -e; \
		mkdir -p $(REMOTE_BACKUP_PATH); \
		docker run --rm -u $(REMOTE_DOCKER_UID):$(REMOTE_DOCKER_GID) \
			-v $(REMOTE_MEDIA_VOLUME):/data:ro -v $(REMOTE_BACKUP_PATH):/backups alpine \
			tar czf /backups/media.$(BACKUP_TIMESTAMP).tgz -C /data . \
	'
	@$(MAKE) --no-print-directory prune-remote-backups

# Apply the generational retention policy to every snapshot group
prune-remote-backups:
	@ssh -p$(REMOTE_PORT) $(REMOTE_HOST) ' \
		docker run --rm -u $(REMOTE_DOCKER_UID):$(REMOTE_DOCKER_GID) \
			-v $(REMOTE_BACKUP_PATH):/backups $(REMOTE_IMAGE) \
			python -m soccertime.backups prune /backups \
				--keep-last $(KEEP_LAST) --keep-daily $(KEEP_DAILY) --keep-monthly $(KEEP_MONTHLY) \
	'

# Copy the remote snapshots here, so losing the server does not take the backups with it
pull-remote-backups:
	@echo "--- Pulling remote snapshots into $(LOCAL_BACKUP_PATH) ---"
	@mkdir -p $(LOCAL_BACKUP_PATH)
	@scp -P$(REMOTE_PORT) "$(REMOTE_HOST):$(REMOTE_BACKUP_PATH)/*" $(LOCAL_BACKUP_PATH)/
	@du -sh $(LOCAL_BACKUP_PATH)

# List the snapshots currently kept on the remote host
list-remote-backups:
	@echo "--- Snapshots on the remote host ---"
	@ssh -p$(REMOTE_PORT) $(REMOTE_HOST) 'ls -lh $(REMOTE_BACKUP_PATH) 2>/dev/null | tail -n +2 || echo "  none"'

# Restore the production database from one of the snapshots.
# Usage: make restore-remote-db BACKUP=db.20260810_203027.sqlite3.gz
restore-remote-db:
	@if [ -z "$(BACKUP)" ]; then \
		echo "Set BACKUP to the snapshot to restore, e.g."; \
		echo "  make restore-remote-db BACKUP=db.20260810_203027.sqlite3.gz"; \
		echo "Run 'make list-remote-backups' to see the available ones."; \
		exit 1; \
	fi
	@echo "--- Restoring remote database from $(BACKUP) ---"
	@ssh -p$(REMOTE_PORT) $(REMOTE_HOST) ' \
		set -e; \
		test -f $(REMOTE_BACKUP_PATH)/$(BACKUP) || { echo Snapshot $(BACKUP) not found; exit 1; }; \
		cd $(REMOTE_DOCKER_PATH); \
		docker compose -f $(REMOTE_DOCKER_COMPOSE_FILE) stop $(REMOTE_SOCCERTIME_SERVICE); \
		docker run --rm -u $(REMOTE_DOCKER_UID):$(REMOTE_DOCKER_GID) -v $(REMOTE_DB_VOLUME):/db -v $(REMOTE_BACKUP_PATH):/backups:ro $(REMOTE_IMAGE) sh -c " \
			python -m soccertime.backups snapshot-db /db/$(REMOTE_DB_FILE_IN_VOLUME) /db/db.$(BACKUP_TIMESTAMP).pre-restore.sqlite3.gz; \
			gunzip -c /backups/$(BACKUP) > /db/$(REMOTE_DB_FILE_IN_VOLUME); \
			rm -f /db/$(REMOTE_DB_FILE_IN_VOLUME)-wal /db/$(REMOTE_DB_FILE_IN_VOLUME)-shm \
		"; \
		docker compose -f $(REMOTE_DOCKER_COMPOSE_FILE) start $(REMOTE_SOCCERTIME_SERVICE) \
	'
	@echo "Database restored and service started."


# Restore flag images whose file went missing from the media volume, re-fetching them
# from the URL each Flag row keeps in its name.
remote-redownload-images:
	@echo "--- Restoring missing flag images on production ---"
	@ssh -p$(REMOTE_PORT) $(REMOTE_HOST) ' \
		cd $(REMOTE_DOCKER_PATH); \
		docker compose -f $(REMOTE_DOCKER_COMPOSE_FILE) exec -T -u $(REMOTE_DOCKER_UID):$(REMOTE_DOCKER_GID) \
			$(REMOTE_SOCCERTIME_SERVICE) python manage.py redownload_images $(ARGS) \
	'

# Import channel links into production, from a local file or straight from a URL.
#
# A local file is external data and never lives in the repository, so it is dropped in the
# shared directory for the run and removed afterwards. It goes through the bind mount
# rather than `docker cp`, because /tmp inside the container is a tmpfs and a copy into it
# is invisible to the process. A URL skips the round trip entirely: the container fetches
# it itself.
# Usage: make remote-import-links SOURCE=newera FILE=~/newera.txt [ARGS=--dry]
#        make remote-import-links SOURCE=tokyo URL=https://host/list.m3u [ARGS=--dry]
remote-import-links:
	@set -e; \
	if [ -z "$(SOURCE)" ] || { [ -z "$(FILE)" ] && [ -z "$(URL)" ]; }; then \
		echo "Usage: make remote-import-links SOURCE=newera FILE=~/newera.txt [ARGS=--dry]"; \
		echo "       make remote-import-links SOURCE=tokyo URL=https://host/list.m3u [ARGS=--dry]"; \
		exit 1; \
	fi; \
	if [ -n "$(FILE)" ] && [ -n "$(URL)" ]; then \
		echo "Pass FILE or URL, not both"; \
		exit 1; \
	fi; \
	if [ -n "$(URL)" ]; then \
		echo "--- Importing $(URL) into production as source $(SOURCE) ---"; \
		ssh -p$(REMOTE_PORT) $(REMOTE_HOST) ' \
			cd $(REMOTE_DOCKER_PATH); \
			docker compose -f $(REMOTE_DOCKER_COMPOSE_FILE) exec -T -u $(REMOTE_DOCKER_UID):$(REMOTE_DOCKER_GID) \
				$(REMOTE_SOCCERTIME_SERVICE) python manage.py addlinksource \
				--source=$(SOURCE) --url="$(URL)" $(ARGS) \
		'; \
	else \
		echo "--- Importing $(FILE) into production as source $(SOURCE) ---"; \
		ssh -p$(REMOTE_PORT) $(REMOTE_HOST) 'mkdir -p $(REMOTE_SHARED_PATH)'; \
		scp -P$(REMOTE_PORT) $(FILE) $(REMOTE_HOST):$(REMOTE_SHARED_PATH)/links-import.txt; \
		ssh -p$(REMOTE_PORT) $(REMOTE_HOST) ' \
			cd $(REMOTE_DOCKER_PATH); \
			docker compose -f $(REMOTE_DOCKER_COMPOSE_FILE) exec -T -u $(REMOTE_DOCKER_UID):$(REMOTE_DOCKER_GID) \
				$(REMOTE_SOCCERTIME_SERVICE) python manage.py addlinksource \
				--source=$(SOURCE) --file=$(CONTAINER_SHARED_PATH)/links-import.txt $(ARGS); \
			status=$$?; \
			rm -f $(REMOTE_SHARED_PATH)/links-import.txt; \
			exit $$status \
		'; \
	fi

# Install, or refresh, the crontab entry that imports a published list into production.
#
# The default schedule is every six hours, at 01:20, 07:20, 13:20 and 19:20, deliberately
# offset from the scraper's own entry so the two never share an hour: a link can only reach
# a channel the scraper has already created, so an import has to follow a scrape rather than
# race it. The scraper runs every four hours (`4 */4 * * *`), so the two drift against each
# other rather than staying in step — the gap between a scrape and the next import runs from
# about seventy minutes to about three and a quarter hours, and every scrape is followed by
# an import well within the day. Close enough is the requirement; "shortly after" was not. The script replaces any entry for the same source and copies every other line
# through untouched.
# Usage: make remote-install-import-cron SOURCE=tokyo URL=https://host/list.m3u
#        make remote-install-import-cron SOURCE=tokyo URL=... CRON_SCHEDULE="0 */6 * * *"
remote-install-import-cron:
	@if [ -z "$(SOURCE)" ] || [ -z "$(URL)" ]; then \
		echo 'Usage: make remote-install-import-cron SOURCE=tokyo URL=https://host/list.m3u [CRON_SCHEDULE="20 1,7,13,19 * * *"]'; \
		exit 1; \
	fi
	@echo "--- Installing the $(SOURCE) import in the remote crontab ---"
	@ssh -p$(REMOTE_PORT) $(REMOTE_HOST) 'sh -s "--source=$(SOURCE)" "$(CRON_SCHEDULE)" "$(IMPORT_CRON_COMMAND)"' < scripts/install-cron-entry.sh

# Keep the logs those cron entries append to from growing without end. Nothing here needs
# root: the deploy user cannot write /etc/logrotate.d, so logrotate runs from a crontab
# entry of its own against a state file in the home directory.
#
# It rotates at an hour no other entry uses. A rotation landing mid-scrape is survivable —
# that is what `delaycompress` is for — but not sharing the hour means it does not happen.
# `/usr/sbin/logrotate` by absolute path: cron's PATH does not carry the sbin directories.
LOGROTATE_SCHEDULE ?= 45 3 * * *
ROTATED_LOGS ?= scrapit.log addlinksource-tokyo.log
remote-install-logrotate:
	@echo "--- Writing the logrotate configuration ---"
	@ssh -p$(REMOTE_PORT) $(REMOTE_HOST) 'sh -s $(ROTATED_LOGS)' < scripts/install-logrotate.sh
	@echo "--- Installing the rotation in the remote crontab ---"
	@ssh -p$(REMOTE_PORT) $(REMOTE_HOST) 'sh -s "logrotate --state" "$(LOGROTATE_SCHEDULE)" "$(LOGROTATE_CRON_COMMAND)"' < scripts/install-cron-entry.sh

# Drop the rendered page cache without running the scraper. Pages are cached for an
# hour, so this is what makes a fix visible immediately after a deploy.
# The page cache lives in a tmpfs inside each container, so with more than one running —
# mid-relay, or a stuck state — clearing "the" cache through `compose exec` reached only
# one of them and the other kept serving stale pages for up to an hour. Every container is
# cleared, and each says so.
remote-clear-cache:
	@echo "--- Clearing the page cache in every running container ---"
	@ssh -p$(REMOTE_PORT) $(REMOTE_HOST) ' \
		set -e; cd $(REMOTE_DOCKER_PATH); \
		ids=$$(docker compose -f $(REMOTE_DOCKER_COMPOSE_FILE) ps -q $(REMOTE_SOCCERTIME_SERVICE)); \
		[ -n "$$ids" ] || { echo "no containers running"; exit 1; }; \
		for id in $$ids; do \
			docker exec -u $(REMOTE_DOCKER_UID):$(REMOTE_DOCKER_GID) $$id \
				python manage.py shell -c "from django.core.cache import cache; cache.clear()"; \
			echo "  cleared $$(echo $$id | cut -c1-12)"; \
		done \
	'
	@echo "Page cache cleared."

# Block until the orchestrator reports the service healthy. A failing health check is
# how the proxy learns to withdraw the route, so an unhealthy container means the site
# is down even though the application itself may be answering.
# Every container must be healthy, not "the" container: the old `case` over the status
# string looked at whatever line matched first, so with two running — mid-relay, or a stuck
# state — one healthy container declared success while the other was still starting, and a
# multi-line status made the report itself misleading.
wait-remote-healthy:
	@echo "--- Waiting for every $(REMOTE_SOCCERTIME_SERVICE) container to report healthy ---"
	@ssh -p$(REMOTE_PORT) $(REMOTE_HOST) ' \
		cd $(REMOTE_DOCKER_PATH); \
		deadline=$$(( $$(date +%s) + $(HEALTH_TIMEOUT) )); \
		while :; do \
			ids=$$(docker compose -f $(REMOTE_DOCKER_COMPOSE_FILE) ps -q $(REMOTE_SOCCERTIME_SERVICE)); \
			if [ -n "$$ids" ]; then \
				all_healthy=yes; \
				for id in $$ids; do \
					state=$$(docker inspect -f "{{.State.Health.Status}}" $$id 2>/dev/null || echo missing); \
					case "$$state" in \
						unhealthy) echo "  $$(echo $$id | cut -c1-12) is unhealthy"; exit 1 ;; \
						healthy) ;; \
						*) all_healthy=no ;; \
					esac; \
				done; \
				if [ "$$all_healthy" = yes ]; then \
					for id in $$ids; do echo "  $$(echo $$id | cut -c1-12) healthy"; done; \
					exit 0; \
				fi; \
			fi; \
			if [ $$(date +%s) -ge $$deadline ]; then \
				echo "  timed out after $(HEALTH_TIMEOUT)s; containers: $${ids:-none}"; exit 1; \
			fi; \
			sleep 2; \
		done \
	'

# Verify a deploy actually works, from outside the server. Fetching from inside the
# container is not enough: when the health check failed, the application still answered
# 200 on localhost while the proxy served 404 to every real visitor. The query string
# bypasses the page cache so each page is rendered fresh.
remote-smoke-test: wait-remote-healthy
	@echo "--- Checking public pages at $(PRODUCTION_URL) ---"
	@failed=""; \
	for path in $(SMOKE_PATHS); do \
		code=$$(curl -s -o /dev/null -w "%{http_code}" -L --max-time 20 "$(PRODUCTION_URL)$$path?smoke=$$$$"); \
		printf "  %-20s %s\n" "$$path" "$$code"; \
		[ "$$code" = "200" ] || failed="$$failed $$path"; \
	done; \
	if [ -n "$$failed" ]; then \
		echo ""; \
		echo "SMOKE TEST FAILED for:$$failed"; \
		echo "The deploy is live and broken. Inspect it with 'make remote-check', 'make"; \
		echo "remote-logs SINCE=10m', or roll back with 'make list-remote-backups' followed"; \
		echo "by 'make restore-remote-db BACKUP=<file>'."; \
		exit 1; \
	fi; \
	echo "Smoke test passed."
	@$(MAKE) --no-print-directory remote-error-check

# Five pages answering 200 is not proof the release is clean: a page can render while another
# path throws, and the deploy has twice reported success over a broken site. This reads the
# new container's own log, from the moment it started, and fails the deploy on any 5xx.
#
# Scoped to that window on purpose. Widen it and unrelated crawler traffic decides whether a
# deploy passes; keep it here and anything found is almost certainly the release. The lines
# are printed rather than counted, because the judgement of whether a 5xx matters is one a
# person makes, not a grep.
remote-error-check:
	@echo "--- Checking every container for server errors since it started ---"
	@errors=$$(ssh -p$(REMOTE_PORT) $(REMOTE_HOST) ' \
		cd $(REMOTE_DOCKER_PATH); \
		for id in $$(docker compose -f $(REMOTE_DOCKER_COMPOSE_FILE) ps -q $(REMOTE_SOCCERTIME_SERVICE)); do \
			started=$$(docker inspect -f "{{.State.StartedAt}}" $$id 2>/dev/null); \
			docker logs --since "$$started" $$id 2>&1 \
				| grep -E "\" $(ERROR_STATUS) " || true; \
		done \
	'); \
	if [ -n "$$errors" ]; then \
		echo "$$errors" | sed "s/^/  /"; \
		echo ""; \
		echo "The container logged server errors since it started. The deploy is live."; \
		echo "Inspect with 'make remote-logs SINCE=10m' and decide whether to roll back."; \
		exit 1; \
	fi; \
	echo "  no 5xx responses logged"

# The admin is the one route on this site that answers to a password, and it faced the
# whole internet with nothing throttling a guess. It is now absent from `urls.py` unless
# `DJANGO_ADMIN_ENABLED` says otherwise, so `/soccertime/admin/` is a 404 rather than a
# login form, and these targets open that window when there is work to do in it.
#
# They edit the local `.env.production` and upload it, rather than editing the copy on the
# server. The deploy uploads the local file, so a server-side toggle would be silently
# undone by the next deploy — and undone in the direction that re-exposes the admin, which
# is exactly the failure nobody would notice. Keeping the local file the source of truth
# means the admin is off after every deploy unless it was deliberately turned on.
#
# Changing an `env_file` entry needs the container recreated, not restarted: a restart
# keeps the environment it was created with.
# Push `.env.production` and put it into effect. Recreating rather than restarting is the
# part that matters: a container keeps the environment it was created with, so a restart
# reports success and changes nothing.
remote-apply-config: upload-config
	@echo "--- Recreating the container so it picks up the new environment ---"
	@ssh -p$(REMOTE_PORT) $(REMOTE_HOST) ' \
		cd $(REMOTE_DOCKER_PATH) && \
		docker compose -f $(REMOTE_DOCKER_COMPOSE_FILE) up -d --force-recreate $(REMOTE_SOCCERTIME_SERVICE) \
	'
	@$(MAKE) --no-print-directory wait-remote-healthy

remote-admin-on:
	@$(MAKE) --no-print-directory remote-admin-set STATE=true
	@echo ""
	@echo "The admin is exposed. Run 'make remote-admin-off' when you are done with it."

remote-admin-off:
	@$(MAKE) --no-print-directory remote-admin-set STATE=false

remote-admin-set:
	@case "$(STATE)" in true|false) ;; *) echo "STATE must be true or false"; exit 1 ;; esac
	@echo "--- Setting DJANGO_ADMIN_ENABLED=$(STATE) in $(ENV_PROD_FILE) ---"
	@sed -i 's/^DJANGO_ADMIN_ENABLED=.*/DJANGO_ADMIN_ENABLED=$(STATE)/' $(ENV_PROD_FILE)
	@grep -qx "DJANGO_ADMIN_ENABLED=$(STATE)" $(ENV_PROD_FILE) \
		|| { echo "Could not set the flag in $(ENV_PROD_FILE); is the line still there?"; exit 1; }
	@$(MAKE) --no-print-directory remote-apply-config
	@code=$$(curl -s -o /dev/null -w "%{http_code}" -L --max-time 20 "$(PRODUCTION_URL)/admin/login/?check=$$$$"); \
	expected=$$([ "$(STATE)" = "true" ] && echo 200 || echo 404); \
	echo "  admin login answers $$code (expected $$expected)"; \
	[ "$$code" = "$$expected" ] || { echo "  the flag did not take effect"; exit 1; }

# The same housekeeping for the development machine, where every `up --build` leaves the
# image it replaced untagged. The label filter matters more here than on the server: this
# machine holds images for unrelated projects, and a blanket `docker image prune` would
# take theirs too.
#
# No `:previous` is kept, unlike the production deploy. A superseded image is worth
# holding there because it is the rollback for a live site; here the way back is to build
# again, and nothing is serving traffic while that happens.
prune-images:
	@echo "--- Removing superseded $(APP_NAME) images from this machine ---"
	@docker image prune -f --filter label=org.opencontainers.image.title=$(APP_NAME)

# Every deploy retags `latest` onto the new build and leaves the previous one untagged,
# so superseded images accumulate. Clearing them has to be scoped rather than a blanket
# `docker image prune`: three of the untagged images on that host carry no `RepoDigests`,
# meaning another service built them there and no registry can hand them back. The label
# restricts this to images built from this Dockerfile.
#
# `:previous` is deliberately kept. Rebuilding from the same commit does not reproduce an
# image, because `python:3-alpine` and pip both resolve afresh — which is exactly how
# Pillow and Django drifted five releases out of date here — so the outgoing image is the
# only rollback that is a known quantity. It runs after the smoke test, so a deploy that
# fails never reaches it and the image it would have replaced stays put.
prune-remote-images:
	@echo "--- Removing superseded $(APP_NAME) images (keeping :previous) ---"
	@ssh -p$(REMOTE_PORT) $(REMOTE_HOST) ' \
		docker image prune -f --filter label=org.opencontainers.image.title=$(APP_NAME) \
	'

# What is left in the application directory now that a deploy sends an image instead of code:
# the checkout the last archive-based deploy unpacked. Nothing reads it — the only reference
# to that directory anywhere on the host is the `include` of the compose file, and the
# containers mount named volumes and `~/shared`, nothing from there — but it still looks like
# the code production runs, and it is whatever commit was deployed the last time a deploy
# uploaded anything. Read during an incident, it would be evidence about the past.
#
# Two files in that same directory are load-bearing and do not look it from there: the host's
# compose `include`s `$(COMPOSE_PROD_FILE)`, and an `include` of a missing file fails every
# `docker compose` command on that machine rather than just this service, and
# `$(ENV_PROD_FILE)` is where the container reads its secret key. So this names what stays
# rather than what goes, and refuses to run at all if either is already absent — the state in
# which "delete everything else" would be a way to finish the job rather than start it.
prune-remote-app-path:
	@echo "--- Removing from $(REMOTE_APP_PATH) everything but the files the host reads ---"
	@ssh -p$(REMOTE_PORT) $(REMOTE_HOST) ' \
		set -e; \
		cd $(REMOTE_APP_PATH); \
		{ test -f $(COMPOSE_PROD_FILE) && test -f $(ENV_PROD_FILE); } || { \
			echo "Refusing: one of the two files the host reads is not here. Run make upload-compose upload-config first."; \
			exit 1; \
		}; \
		find . -mindepth 1 -maxdepth 1 ! -name "$(COMPOSE_PROD_FILE)" ! -name "$(ENV_PROD_FILE)" -print; \
		find . -mindepth 1 -maxdepth 1 ! -name "$(COMPOSE_PROD_FILE)" ! -name "$(ENV_PROD_FILE)" -exec rm -rf {} +; \
		echo "--- What is left ---"; \
		ls -A \
	'

# The local production replica, whose stack is three files. Kept here so the incantation is
# reviewable, which is the same reason the remote operations live here.
REPLICA_COMPOSE = -f compose.yaml -f compose.production.yaml -f compose.production.local.yaml
REPLICA_SERVICE ?= soccertime-web
MANAGE ?= migrate

# Run a management command against the replica as whoever owns its database.
#
# The replica's volume comes from a production copy, so its files belong to production's UID
# while `.env` sets this machine's — 1000 against 1001 here. Running as the wrong one fails
# with `attempt to write a readonly database`, which says nothing about ownership, and it
# cannot be hardcoded because the number changes with whichever dump was loaded. So it is
# read off the file itself.
#
#   make replica-migrate
#   make replica-manage MANAGE="showmigrations soccertime"
# The replica's database volume carries a copy of production's, so its files belong to
# production's UID while the replica runs as this machine's — 1000 against 1001 here. That
# mismatch used to cost only writes; with the write-ahead log it costs reads too, because
# reading the journal means creating the shared-memory index beside it. The stack comes up
# healthy and answers 500 to every page that touches the database, which reads like a broken
# deploy rather than a permissions problem.
#
# The user cannot simply be production's: `./media` and `./static` are bind mounts of this
# working copy and belong to whoever checked it out, so the replica has to run as them. So
# the volume is handed over instead, the same way `remote_deploy` hands the static volume to
# whoever production runs as. Doing it here rather than leaving it to be remembered is the
# point: the README's bare `docker compose up` is what produced the 500s.
REPLICA_DB_VOLUME ?= $(notdir $(CURDIR))_soccertime-db

# The steps run in the order `remote_deploy` runs them, which is the other half of what
# makes this a rehearsal: static files are collected **before** anything serves them. A
# process reads the manifest once, at startup, and caches it for its whole life — so
# collecting after `up` leaves the container answering 500 to every page while its health
# check stays green. That is the incident `CLAUDE.md` documents, and doing it in the wrong
# order here reproduced it exactly.
replica-up: replica-build replica-serve

# Rehearse the artefact production will run rather than a local rebuild of it. Two builds of
# one commit are not the same image — the base image and every wheel resolve afresh — so once
# the question is "does the published image serve?", building here answers a different one.
# Same tag as the build, so everything downstream is untouched.
replica-up-published: replica-pull replica-serve

replica-build:
	@echo "--- Building the replica image ---"
	@docker compose $(REPLICA_COMPOSE) build $(REPLICA_SERVICE)

replica-pull:
	@echo "--- Pulling $(GHCR_IMAGE):$(DEPLOY_TAG) ---"
	@docker pull $(GHCR_IMAGE):$(DEPLOY_TAG)
	@docker tag $(GHCR_IMAGE):$(DEPLOY_TAG) $(APP_NAME):replica
	@docker rmi $(GHCR_IMAGE):$(DEPLOY_TAG)

replica-serve:
	@echo "--- Handing the database volume to the user the replica runs as ---"
	@docker run --rm -v $(REPLICA_DB_VOLUME):/db alpine chown -R $(DOCKER_UID):$(DOCKER_GID) /db
	@echo "--- Collecting static files, before anything serves them ---"
	@docker compose $(REPLICA_COMPOSE) run --rm --no-deps -u $(DOCKER_UID):$(DOCKER_GID) \
		$(REPLICA_SERVICE) python manage.py collectstatic --noinput
	@echo "--- Starting the replica ---"
	@docker compose $(REPLICA_COMPOSE) up -d traefik $(REPLICA_SERVICE) soccertime-nginx

replica-manage:
	@owner=$$(docker compose $(REPLICA_COMPOSE) exec -T $(REPLICA_SERVICE) \
		stat -c "%u:%g" /code/db/db.sqlite3 2>/dev/null | tr -d "\r"); \
	if [ -z "$$owner" ]; then \
		echo "The replica is not running. Start it with 'make replica-up'."; \
		exit 1; \
	fi; \
	echo "--- Running '$(MANAGE)' on the replica as $$owner ---"; \
	docker compose $(REPLICA_COMPOSE) exec -T -u $$owner $(REPLICA_SERVICE) \
		python manage.py $(MANAGE)

replica-migrate:
	@$(MAKE) --no-print-directory replica-manage MANAGE=migrate

# The same relay production runs, against the local replica — one file, two callers, so the
# rehearsal cannot diverge from the real thing. Run it from any state: one container is the
# normal handover, two rehearses healing an interrupted deploy, zero a cold start.
replica-relay:
	@COMPOSE_CMD="docker compose $(REPLICA_COMPOSE)" \
	HEALTH_TIMEOUT=$(HEALTH_TIMEOUT) PROXY_SETTLE_SECONDS=$(PROXY_SETTLE_SECONDS) \
	sh -s $(REPLICA_SERVICE) soccertime:replica < scripts/relay.sh

# Refresh the images the host really does fetch. Plain `docker compose pull` fails there:
# `soccertime` and `frankenshop` are built on the host and exist in no registry, so it asks
# for them, is denied, and exits non-zero — the four images that are genuinely remote get
# pulled but the command still reports failure.
#
# `--ignore-buildable` skips exactly the services that declare a `build:`, which both of those
# do, and nothing else. Not `--ignore-pull-failures`, which would also swallow a real registry
# outage for the images that matter. This project's own service additionally sets
# `pull_policy: never`, so a bare `pull` no longer trips over it; the flag is what covers the
# neighbouring stack the host includes and this repository does not own.
# `make remote-pull PULL_FLAGS=` runs the bare command, which is how to check whether the
# services still need the flag or now declare `pull_policy: never` for themselves.
PULL_FLAGS ?= --ignore-buildable

remote-pull:
	@echo "--- Pulling the images the host fetches $(if $(PULL_FLAGS),(with $(PULL_FLAGS)),(no flags)) ---"
	@ssh -p$(REMOTE_PORT) $(REMOTE_HOST) ' \
		cd $(REMOTE_DOCKER_PATH); \
		docker compose -f $(REMOTE_DOCKER_COMPOSE_FILE) pull $(PULL_FLAGS) \
	'

# What is actually running out there, containers and images. Read-only, and here rather than
# in an ad-hoc SSH command for the same reason as everything else: so it is reviewable.
remote-ps:
	@echo "--- Containers on the remote host ---"
	@ssh -p$(REMOTE_PORT) $(REMOTE_HOST) ' \
		cd $(REMOTE_DOCKER_PATH); \
		docker compose -f $(REMOTE_DOCKER_COMPOSE_FILE) ps --format "table {{.Name}}\t{{.Image}}\t{{.Status}}"; \
		echo; echo "--- Static volume ---"; \
		docker run --rm -v $(REMOTE_STATIC_VOLUME):/data alpine \
			sh -c "printf \"   %s in %s files\\n\" \$$(du -sh /data | cut -f1) \$$(find /data -type f | wc -l)"; \
		echo; echo "--- Proxy in front of it ---"; \
		docker inspect -f "{{.Config.Image}}" traefik 2>/dev/null; \
		docker exec traefik traefik version 2>/dev/null | head -2; \
		echo; echo "--- Compose, and which services it would have to build rather than pull ---"; \
		docker compose version --short; \
		docker compose -f $(REMOTE_DOCKER_COMPOSE_FILE) config --format json \
			| python3 -c "import json,sys; s=json.load(sys.stdin)[\"services\"]; [print(\"  \", n, \"build\" if \"build\" in v else \"pull\", v.get(\"image\",\"\"), \"pull_policy=\" + v.get(\"pull_policy\",\"(default)\")) for n,v in s.items()]" \
	'

# Read the application's own logs. `CLAUDE.md` requires checking them for 500s after every
# deploy and, separately, that production operations live here rather than in an ad-hoc SSH
# command — and until this existed the two instructions could not both be obeyed, so the
# evidence that nothing was throwing had to come indirectly from fetching pages.
#
#   make remote-logs                     the last 200 lines
#   make remote-logs SINCE=10m           only what came after a deploy
#   make remote-logs GREP=" 500 "        only the server errors
remote-logs:
	@echo "--- Logs for $(REMOTE_SOCCERTIME_SERVICE) ---"
	@ssh -p$(REMOTE_PORT) $(REMOTE_HOST) ' \
		cd $(REMOTE_DOCKER_PATH); \
		docker compose -f $(REMOTE_DOCKER_COMPOSE_FILE) logs \
			--tail $(LOG_TAIL) $(if $(LOG_SINCE),--since $(LOG_SINCE),) --no-log-prefix \
			$(REMOTE_SOCCERTIME_SERVICE) \
	' | { [ -n "$(LOG_GREP)" ] && grep -- "$(LOG_GREP)" || cat; }

# Run Django's deployment checks against the running production container
remote-check:
	@echo "--- Running deployment checks on production ---"
	@ssh -p$(REMOTE_PORT) $(REMOTE_HOST) ' \
		cd $(REMOTE_DOCKER_PATH); \
		docker compose -f $(REMOTE_DOCKER_COMPOSE_FILE) exec -T -u $(REMOTE_DOCKER_UID):$(REMOTE_DOCKER_GID) \
			$(REMOTE_SOCCERTIME_SERVICE) python manage.py check --deploy --fail-level WARNING \
	'

# Download database from remote DB volume (with local backup)
download-db:
	@echo "--- Downloading database from remote volume ---"
	@if [ -f "$(LOCAL_DB_PATH)" ]; then \
		echo "Snapshotting local database to $(LOCAL_DB_PATH)$(BACKUP_SUFFIX).gz"; \
		python3 -m soccertime.backups snapshot-db $(LOCAL_DB_PATH) $(LOCAL_DB_PATH)$(BACKUP_SUFFIX).gz; \
	fi
	@mkdir -p $(dir $(LOCAL_DB_PATH))
	ssh -p$(REMOTE_PORT) $(REMOTE_HOST) 'docker run --rm -u $(REMOTE_DOCKER_UID):$(REMOTE_DOCKER_GID) -v $(REMOTE_DB_VOLUME):/db -v /tmp:/to $(REMOTE_IMAGE) python -m soccertime.backups snapshot-db /db/$(REMOTE_DB_FILE_IN_VOLUME) /to/$(APP_NAME)-db.sqlite3.gz'
	scp -P$(REMOTE_PORT) $(REMOTE_HOST):/tmp/$(APP_NAME)-db.sqlite3.gz /tmp/$(APP_NAME)-db.sqlite3.gz
	ssh -p$(REMOTE_PORT) $(REMOTE_HOST) 'rm -f /tmp/$(APP_NAME)-db.sqlite3.gz'
	@docker compose stop web >/dev/null 2>&1 || true
	gunzip -c /tmp/$(APP_NAME)-db.sqlite3.gz > $(LOCAL_DB_PATH)
	@rm -f $(LOCAL_DB_PATH)-wal $(LOCAL_DB_PATH)-shm /tmp/$(APP_NAME)-db.sqlite3.gz
	@docker compose start web >/dev/null 2>&1 || true
	@echo "Database downloaded successfully."

# Upload database to remote DB volume (with remote backup)
upload-db:
	@echo "--- Uploading database to remote volume ---"
	python3 -m soccertime.backups snapshot-db $(LOCAL_DB_PATH) /tmp/$(APP_NAME)-db.sqlite3.gz
	scp -P$(REMOTE_PORT) /tmp/$(APP_NAME)-db.sqlite3.gz $(REMOTE_HOST):~/$(APP_NAME)-db.sqlite3.gz
	@ssh -p$(REMOTE_PORT) $(REMOTE_HOST) ' \
		set -e; \
		cd $(REMOTE_DOCKER_PATH); \
		docker compose -f $(REMOTE_DOCKER_COMPOSE_FILE) stop $(REMOTE_SOCCERTIME_SERVICE); \
		docker run --rm -u $(REMOTE_DOCKER_UID):$(REMOTE_DOCKER_GID) -v $(REMOTE_DB_VOLUME):/data -v $$HOME:/src $(REMOTE_IMAGE) sh -c " \
			if [ -f /data/$(REMOTE_DB_FILE_IN_VOLUME) ]; then \
				echo Snapshotting the database being replaced; \
				python -m soccertime.backups snapshot-db /data/$(REMOTE_DB_FILE_IN_VOLUME) /data/db.$(BACKUP_TIMESTAMP).pre-upload.sqlite3.gz; \
			fi; \
			gunzip -c /src/$(APP_NAME)-db.sqlite3.gz > /data/$(REMOTE_DB_FILE_IN_VOLUME); \
			rm -f /data/$(REMOTE_DB_FILE_IN_VOLUME)-wal /data/$(REMOTE_DB_FILE_IN_VOLUME)-shm \
		"; \
		docker compose -f $(REMOTE_DOCKER_COMPOSE_FILE) start $(REMOTE_SOCCERTIME_SERVICE); \
		rm -f ~/$(APP_NAME)-db.sqlite3.gz \
	'
	@rm -f /tmp/$(APP_NAME)-db.sqlite3.gz
	@echo "Database uploaded successfully."

# Download cache from remote DB volume (with local backup)
download-requests-cache:
	@echo "--- Downloading requests cache from remote volume ---"
	@if [ -f "$(LOCAL_CACHE_PATH)" ]; then \
		echo "Backing up local cache to $(LOCAL_CACHE_PATH)$(BACKUP_SUFFIX)"; \
		cp $(LOCAL_CACHE_PATH) $(LOCAL_CACHE_PATH)$(BACKUP_SUFFIX); \
	fi
	ssh -p$(REMOTE_PORT) $(REMOTE_HOST) 'HOST_UID=$$(id -u); HOST_GID=$$(id -g); docker run --rm -v $(REMOTE_DB_VOLUME):/from -v /tmp:/to alpine sh -c "cp /from/$(REMOTE_CACHE_FILE_IN_VOLUME) /to/$(APP_NAME)-requests-cache.sqlite && chown $$HOST_UID:$$HOST_GID /to/$(APP_NAME)-requests-cache.sqlite"'
	scp -P$(REMOTE_PORT) $(REMOTE_HOST):/tmp/$(APP_NAME)-requests-cache.sqlite $(LOCAL_CACHE_PATH)
	ssh -p$(REMOTE_PORT) $(REMOTE_HOST) 'rm -f /tmp/$(APP_NAME)-requests-cache.sqlite'
	@echo "Requests cache downloaded successfully."

# Upload cache to remote DB volume (with remote backup)
upload-requests-cache:
	@echo "--- Uploading requests cache to remote volume ---"
	scp -P$(REMOTE_PORT) $(LOCAL_CACHE_PATH) $(REMOTE_HOST):/tmp/$(APP_NAME)-requests-cache.sqlite
	@ssh -p$(REMOTE_PORT) $(REMOTE_HOST) ' \
		set -e; \
		docker run --rm -v $(REMOTE_DB_VOLUME):/data -v /tmp:/tmp alpine sh -c " \
			if [ -f /data/$(REMOTE_CACHE_FILE_IN_VOLUME) ]; then \
				echo Backing up remote cache; \
				cp /data/$(REMOTE_CACHE_FILE_IN_VOLUME) /data/$(REMOTE_CACHE_FILE_IN_VOLUME).backup.$$(date +%Y%m%d_%H%M%S); \
			fi; \
			cp /tmp/$(APP_NAME)-requests-cache.sqlite /data/$(REMOTE_CACHE_FILE_IN_VOLUME); \
			chown $(REMOTE_DOCKER_UID):$(REMOTE_DOCKER_GID) /data/$(REMOTE_CACHE_FILE_IN_VOLUME) \
		"; \
		rm -f /tmp/$(APP_NAME)-requests-cache.sqlite \
	'
	@echo "Requests cache uploaded successfully."

# Download media directory from remote media volume (with local backup)
download-media:
	@echo "--- Downloading media from remote volume ---"
	@if [ -d "$(LOCAL_MEDIA_PATH)" ]; then \
		echo "Backing up local media to $(LOCAL_MEDIA_PATH)$(BACKUP_SUFFIX)"; \
		cp -r $(LOCAL_MEDIA_PATH) $(LOCAL_MEDIA_PATH)$(BACKUP_SUFFIX); \
	fi
	@mkdir -p $(LOCAL_MEDIA_PATH)
	ssh -p$(REMOTE_PORT) $(REMOTE_HOST) 'HOST_UID=$$(id -u); HOST_GID=$$(id -g); docker run --rm -v $(REMOTE_MEDIA_VOLUME):/from -v /tmp:/to alpine sh -c "cd /from && tar czf /to/$(APP_NAME)-media.tgz . && chown $$HOST_UID:$$HOST_GID /to/$(APP_NAME)-media.tgz"'
	scp -P$(REMOTE_PORT) $(REMOTE_HOST):/tmp/$(APP_NAME)-media.tgz /tmp/$(APP_NAME)-media.tgz
	@tar xzf /tmp/$(APP_NAME)-media.tgz -C $(LOCAL_MEDIA_PATH)
	@rm -f /tmp/$(APP_NAME)-media.tgz
	ssh -p$(REMOTE_PORT) $(REMOTE_HOST) 'rm -f /tmp/$(APP_NAME)-media.tgz'
	@echo "Media downloaded successfully."

# Upload media directory to remote media volume (with remote backup)
upload-media:
	@echo "--- Uploading media to remote volume ---"
	@tar czf /tmp/$(APP_NAME)-media.tgz -C $(LOCAL_MEDIA_PATH) .
	scp -P$(REMOTE_PORT) /tmp/$(APP_NAME)-media.tgz $(REMOTE_HOST):/tmp/$(APP_NAME)-media.tgz
	@ssh -p$(REMOTE_PORT) $(REMOTE_HOST) ' \
		set -e; \
		docker run --rm -v $(REMOTE_MEDIA_VOLUME):/data -v /tmp:/tmp alpine sh -c " \
			if [ \"$$(ls -A /data 2>/dev/null)\" ]; then \
				echo Backing up remote media; \
				tar czf /tmp/$(APP_NAME)-media.backup.$$(date +%Y%m%d_%H%M%S).tgz -C /data .; \
			fi && \
			find /data -mindepth 1 -maxdepth 1 -exec rm -rf {} + && \
			tar xzf /tmp/$(APP_NAME)-media.tgz -C /data && \
			chown -R $(REMOTE_DOCKER_UID):$(REMOTE_DOCKER_GID) /data \
		"; \
		rm -f /tmp/$(APP_NAME)-media.tgz \
	'
	@rm -f /tmp/$(APP_NAME)-media.tgz
	@echo "Media uploaded successfully."

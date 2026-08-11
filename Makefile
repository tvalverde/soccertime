.PHONY: help typecheck screenshot prune-images remote-apply-config remote-admin-on remote-admin-off remote-admin-set deploy-production archive_app upload_files remote_deploy clean_local_archive upload-only upload-config remote-restart remote-scrape remote-check remote-smoke-test wait-remote-healthy remote-clear-cache remote-redownload-images remote-import-links prune-remote-images backup-remote-db backup-remote-media prune-remote-backups pull-remote-backups list-remote-backups restore-remote-db download-db upload-db download-requests-cache upload-requests-cache download-media upload-media test test-integration test-cov lint lint-fix format

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
	@echo "DEPLOY:"
	@echo "  deploy-production    Full deploy (upload code + run on remote orchestrator)"
	@echo "  upload-only          Upload code and .env.production without running deploy"
	@echo "  upload-config        Upload only .env.production"
	@echo "  remote-restart       Rebuild/recreate remote services via orchestrator"
	@echo "  remote-scrape        Run the scraper on the remote server and clear cache"
	@echo "  remote-check         Run Django's deployment checks on production"
	@echo "  remote-smoke-test    Verify a live deploy from outside (health + public pages)"
	@echo "  remote-clear-cache   Drop the rendered page cache on production"
	@echo "  remote-redownload-images  Restore flag images missing from the media volume"
	@echo "  remote-import-links  Import channel links (SOURCE=, FILE=, ARGS=--dry)"
	@echo "  prune-remote-images  Drop this project's superseded images, keeping :previous"
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
PRODUCTION_URL ?= https://www.mojon.es/soccertime
SMOKE_PATHS ?= /healthz/ /favorites/ /agenda/ /competitions/ /channels/
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

# Application archive to upload
ARCHIVE_NAME = $(APP_NAME).tgz
LOCAL_ARCHIVE_PATH = /tmp/$(ARCHIVE_NAME)

# Configuration files to upload
ENV_PROD_FILE = .env.production

# Main target for production deployment.
# The snapshots run before remote_deploy, which is what applies the migrations,
# and the smoke test runs last so a deploy that leaves the site broken fails loudly.
deploy-production: archive_app upload_files backup-remote-db backup-remote-media remote_deploy clean_local_archive remote-smoke-test prune-remote-images
	@echo "Deployment process completed successfully."

# Target to archive application files locally
archive_app:
	@echo "--- Archiving application files ---"
	git archive --format=tgz -o $(LOCAL_ARCHIVE_PATH) HEAD

# Target to upload files to remote server
upload_files:
	@echo "--- Uploading application archive and .env.production ---"
	@ssh -p$(REMOTE_PORT) $(REMOTE_HOST) 'mkdir -p $(REMOTE_APP_PATH)'
	scp -P$(REMOTE_PORT) $(LOCAL_ARCHIVE_PATH) $(REMOTE_HOST):$(REMOTE_APP_PATH)/
	@if [ -f "$(ENV_PROD_FILE)" ]; then \
		echo "Uploading $(ENV_PROD_FILE)..."; \
		scp -P$(REMOTE_PORT) $(ENV_PROD_FILE) $(REMOTE_HOST):$(REMOTE_APP_PATH)/; \
	else \
		echo "Warning: $(ENV_PROD_FILE) not found locally. Skipping upload."; \
	fi

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
# through `exec` afterwards. Static filenames carry a content hash, and the manifest that
# maps plain names to hashed ones is read once, the first time a template renders a
# `{% static %}` tag. Collecting afterwards meant the new process could read a manifest
# that was still missing or half-written and then hold it for its whole life: every page
# answered 500 while `/healthz/` — which renders no template — stayed green, so the
# container looked healthy with the site down. Finishing the collection first removes the
# window rather than papering over it with a second restart.
remote_deploy:
	@echo "--- Initiating remote deployment via SSH ---"
	ssh -p$(REMOTE_PORT) $(REMOTE_HOST) ' \
		set -e && \
		cd $(REMOTE_APP_PATH) && \
		echo "--- Extracting new application code ---" && \
		tar zxfv $(ARCHIVE_NAME) && \
		rm $(ARCHIVE_NAME) && \
		cd $(REMOTE_DOCKER_PATH) && \
		{ docker image inspect $(APP_NAME):latest >/dev/null 2>&1 \
			&& docker tag $(APP_NAME):latest $(APP_NAME):previous || true; } && \
		echo "--- Building the new image ---" && \
		docker compose -f $(REMOTE_DOCKER_COMPOSE_FILE) build $(REMOTE_SOCCERTIME_SERVICE) && \
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
		echo "--- Recreating services via orchestrator ---" && \
		docker compose -f $(REMOTE_DOCKER_COMPOSE_FILE) up -d --remove-orphans $(REMOTE_SOCCERTIME_SERVICE) && \
		echo "--- Applying database migrations ---" && \
		docker compose -f $(REMOTE_DOCKER_COMPOSE_FILE) exec -u $(REMOTE_DOCKER_UID):$(REMOTE_DOCKER_GID) $(REMOTE_SOCCERTIME_SERVICE) python manage.py migrate --noinput \
	'

# Target to clean up local temporary archive after upload
clean_local_archive:
	@echo "--- Cleaning up local archive ---"
	rm $(LOCAL_ARCHIVE_PATH)

# Upload and unpack the code without building, migrating or restarting anything.
# The archive has to be extracted here too: leaving it packed means a later
# remote-restart quietly rebuilds the image from the previous version.
upload-only: archive_app upload_files clean_local_archive
	@ssh -p$(REMOTE_PORT) $(REMOTE_HOST) ' \
		set -e; \
		cd $(REMOTE_APP_PATH); \
		tar zxf $(ARCHIVE_NAME); \
		rm $(ARCHIVE_NAME) \
	'
	@echo "Files uploaded and extracted. No build, migration or restart executed."

# Target to upload only configuration file (.env.production)
upload-config:
	@echo "--- Uploading configuration file only ---"
	@if [ -f "$(ENV_PROD_FILE)" ]; then \
		echo "Uploading $(ENV_PROD_FILE)..."; \
		scp -P$(REMOTE_PORT) $(ENV_PROD_FILE) $(REMOTE_HOST):$(REMOTE_APP_PATH)/; \
		echo "Configuration file uploaded successfully."; \
	else \
		echo "Warning: $(ENV_PROD_FILE) not found locally. Nothing uploaded."; \
	fi

# Target to rebuild/recreate remote services without uploading
remote-restart:
	@echo "--- Rebuilding and restarting remote services (safe up) ---"
	ssh -p$(REMOTE_PORT) $(REMOTE_HOST) ' \
		set -e; \
		cd $(REMOTE_DOCKER_PATH); \
		docker compose -f $(REMOTE_DOCKER_COMPOSE_FILE) up -d --build --remove-orphans $(REMOTE_SOCCERTIME_SERVICE); \
		echo "Services rebuilt/restarted successfully." \
	'

# Target to run the scraper on the remote production server and clear the cache
remote-scrape:
	@echo "--- Running remote scraper and clearing cache ---"
	ssh -p$(REMOTE_PORT) $(REMOTE_HOST) ' \
		set -e; \
		cd $(REMOTE_DOCKER_PATH); \
		echo "Running scraper..."; \
		docker compose -f $(REMOTE_DOCKER_COMPOSE_FILE) exec -u $(REMOTE_DOCKER_UID):$(REMOTE_DOCKER_GID) $(REMOTE_SOCCERTIME_SERVICE) python manage.py scrapit; \
		echo "Clearing cache..."; \
		docker compose -f $(REMOTE_DOCKER_COMPOSE_FILE) exec -u $(REMOTE_DOCKER_UID):$(REMOTE_DOCKER_GID) $(REMOTE_SOCCERTIME_SERVICE) python manage.py shell -c "from django.core.cache import cache; cache.clear()"; \
		echo "Remote scrape and cache clear completed successfully." \
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
backup-remote-db:
	@echo "--- Backing up remote database ---"
	@ssh -p$(REMOTE_PORT) $(REMOTE_HOST) ' \
		set -e; \
		mkdir -p $(REMOTE_BACKUP_PATH); \
		docker run --rm -u $(REMOTE_DOCKER_UID):$(REMOTE_DOCKER_GID) \
			-v $(REMOTE_DB_VOLUME):/db:ro -v $(REMOTE_BACKUP_PATH):/backups $(REMOTE_IMAGE) \
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
		docker run --rm -v $(REMOTE_DB_VOLUME):/db -v $(REMOTE_BACKUP_PATH):/backups:ro alpine sh -c " \
			test -f /backups/$(BACKUP) || { echo Snapshot $(BACKUP) not found; exit 1; }; \
			cp /db/$(REMOTE_DB_FILE_IN_VOLUME) /db/$(REMOTE_DB_FILE_IN_VOLUME).pre-restore; \
			gunzip -c /backups/$(BACKUP) > /db/$(REMOTE_DB_FILE_IN_VOLUME); \
			chown $(REMOTE_DOCKER_UID):$(REMOTE_DOCKER_GID) /db/$(REMOTE_DB_FILE_IN_VOLUME) \
		"; \
		cd $(REMOTE_DOCKER_PATH); \
		docker compose -f $(REMOTE_DOCKER_COMPOSE_FILE) restart $(REMOTE_SOCCERTIME_SERVICE) \
	'
	@echo "Database restored and service restarted."


# Restore flag images whose file went missing from the media volume, re-fetching them
# from the URL each Flag row keeps in its name.
remote-redownload-images:
	@echo "--- Restoring missing flag images on production ---"
	@ssh -p$(REMOTE_PORT) $(REMOTE_HOST) ' \
		cd $(REMOTE_DOCKER_PATH); \
		docker compose -f $(REMOTE_DOCKER_COMPOSE_FILE) exec -T -u $(REMOTE_DOCKER_UID):$(REMOTE_DOCKER_GID) \
			$(REMOTE_SOCCERTIME_SERVICE) python manage.py redownload_images $(ARGS) \
	'

# Import channel links from a local file into production. The file is external data and
# never lives in the repository, so it is dropped in the shared directory for the run and
# removed afterwards. It goes through the bind mount rather than `docker cp`, because
# /tmp inside the container is a tmpfs and a copy into it is invisible to the process.
# Usage: make remote-import-links SOURCE=newera FILE=~/newera.txt [ARGS=--dry]
remote-import-links:
	@if [ -z "$(SOURCE)" ] || [ -z "$(FILE)" ]; then \
		echo "Usage: make remote-import-links SOURCE=newera FILE=~/newera.txt [ARGS=--dry]"; \
		exit 1; \
	fi
	@echo "--- Importing $(FILE) into production as source $(SOURCE) ---"
	@ssh -p$(REMOTE_PORT) $(REMOTE_HOST) 'mkdir -p $(REMOTE_SHARED_PATH)'
	@scp -P$(REMOTE_PORT) $(FILE) $(REMOTE_HOST):$(REMOTE_SHARED_PATH)/links-import.txt
	@ssh -p$(REMOTE_PORT) $(REMOTE_HOST) ' \
		cd $(REMOTE_DOCKER_PATH); \
		docker compose -f $(REMOTE_DOCKER_COMPOSE_FILE) exec -T -u $(REMOTE_DOCKER_UID):$(REMOTE_DOCKER_GID) \
			$(REMOTE_SOCCERTIME_SERVICE) python manage.py addlinksource \
			--source=$(SOURCE) --file=$(CONTAINER_SHARED_PATH)/links-import.txt $(ARGS); \
		status=$$?; \
		rm -f $(REMOTE_SHARED_PATH)/links-import.txt; \
		exit $$status \
	'

# Drop the rendered page cache without running the scraper. Pages are cached for an
# hour, so this is what makes a fix visible immediately after a deploy.
remote-clear-cache:
	@echo "--- Clearing the remote page cache ---"
	@ssh -p$(REMOTE_PORT) $(REMOTE_HOST) ' \
		cd $(REMOTE_DOCKER_PATH); \
		docker compose -f $(REMOTE_DOCKER_COMPOSE_FILE) exec -T -u $(REMOTE_DOCKER_UID):$(REMOTE_DOCKER_GID) \
			$(REMOTE_SOCCERTIME_SERVICE) python manage.py shell -c "from django.core.cache import cache; cache.clear()" \
	'
	@echo "Page cache cleared."

# Block until the orchestrator reports the service healthy. A failing health check is
# how the proxy learns to withdraw the route, so an unhealthy container means the site
# is down even though the application itself may be answering.
wait-remote-healthy:
	@echo "--- Waiting for $(REMOTE_SOCCERTIME_SERVICE) to report healthy ---"
	@ssh -p$(REMOTE_PORT) $(REMOTE_HOST) ' \
		cd $(REMOTE_DOCKER_PATH); \
		deadline=$$(( $$(date +%s) + $(HEALTH_TIMEOUT) )); \
		while :; do \
			status=$$(docker compose -f $(REMOTE_DOCKER_COMPOSE_FILE) ps $(REMOTE_SOCCERTIME_SERVICE) --format "{{.Status}}"); \
			case "$$status" in \
				*unhealthy*) echo "  $$status"; exit 1 ;; \
				*healthy*)   echo "  $$status"; exit 0 ;; \
			esac; \
			if [ $$(date +%s) -ge $$deadline ]; then echo "  timed out after $(HEALTH_TIMEOUT)s: $$status"; exit 1; fi; \
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
		echo "The deploy is live and broken. Inspect it with 'make remote-check' and the"; \
		echo "container logs, or roll back with 'make list-remote-backups' followed by"; \
		echo "'make restore-remote-db BACKUP=<file>'."; \
		exit 1; \
	fi; \
	echo "Smoke test passed."

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
		echo "Backing up local database to $(LOCAL_DB_PATH)$(BACKUP_SUFFIX)"; \
		cp $(LOCAL_DB_PATH) $(LOCAL_DB_PATH)$(BACKUP_SUFFIX); \
	fi
	@mkdir -p $(dir $(LOCAL_DB_PATH))
	ssh -p$(REMOTE_PORT) $(REMOTE_HOST) 'HOST_UID=$$(id -u); HOST_GID=$$(id -g); docker run --rm -v $(REMOTE_DB_VOLUME):/from -v /tmp:/to alpine sh -c "cp /from/$(REMOTE_DB_FILE_IN_VOLUME) /to/$(APP_NAME)-db.sqlite3 && chown $$HOST_UID:$$HOST_GID /to/$(APP_NAME)-db.sqlite3"'
	scp -P$(REMOTE_PORT) $(REMOTE_HOST):/tmp/$(APP_NAME)-db.sqlite3 $(LOCAL_DB_PATH)
	ssh -p$(REMOTE_PORT) $(REMOTE_HOST) 'rm -f /tmp/$(APP_NAME)-db.sqlite3'
	@echo "Database downloaded successfully."

# Upload database to remote DB volume (with remote backup)
upload-db:
	@echo "--- Uploading database to remote volume ---"
	scp -P$(REMOTE_PORT) $(LOCAL_DB_PATH) $(REMOTE_HOST):~/$(APP_NAME)-db.sqlite3
	@ssh -p$(REMOTE_PORT) $(REMOTE_HOST) ' \
		set -e; \
		docker run --rm -v $(REMOTE_DB_VOLUME):/data -v $$HOME:/src alpine sh -c " \
			if [ -f /data/$(REMOTE_DB_FILE_IN_VOLUME) ]; then \
				echo Backing up remote database; \
				cp /data/$(REMOTE_DB_FILE_IN_VOLUME) /data/$(REMOTE_DB_FILE_IN_VOLUME).backup.$$(date +%Y%m%d_%H%M%S); \
			fi; \
			cp /src/$(APP_NAME)-db.sqlite3 /data/$(REMOTE_DB_FILE_IN_VOLUME); \
			chown $(REMOTE_DOCKER_UID):$(REMOTE_DOCKER_GID) /data/$(REMOTE_DB_FILE_IN_VOLUME) \
		"; \
		rm -f ~/$(APP_NAME)-db.sqlite3 \
	'
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

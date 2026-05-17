.PHONY: help deploy-production archive_app upload_files remote_deploy clean_local_archive upload-only upload-config remote-restart download-db upload-db download-requests-cache upload-requests-cache download-media upload-media test test-cov lint lint-fix format

# Default target: show help
.DEFAULT_GOAL := help

# Show help with all available commands
help:
	@echo "Soccertime - Deployment and management commands"
	@echo ""
	@echo "USAGE: make <target>"
	@echo ""
	@echo "DEVELOPMENT:"
	@echo "  test                 Run tests"
	@echo "  test-cov             Run tests with coverage report"
	@echo "  lint                 Check code for linting errors"
	@echo "  lint-fix             Fix auto-fixable linting errors"
	@echo "  format               Format code with ruff"
	@echo ""
	@echo "DEPLOY:"
	@echo "  deploy-production    Full deploy (upload code + run on remote orchestrator)"
	@echo "  upload-only          Upload code and .env.production without running deploy"
	@echo "  upload-config        Upload only .env.production"
	@echo "  remote-restart       Rebuild/recreate remote services via orchestrator"
	@echo ""
	@echo "DATABASE (SQLite in Docker volume):"
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

# === Development Commands ===

# Run tests
test:
	@docker compose exec -u $(DOCKER_UID):$(DOCKER_GID) web pytest

# Run tests with coverage report
test-cov:
	@docker compose exec -u $(DOCKER_UID):$(DOCKER_GID) web pytest --cov --cov-report=term-missing

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

# Main target for production deployment
deploy-production: archive_app upload_files remote_deploy clean_local_archive
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
remote_deploy:
	@echo "--- Initiating remote deployment via SSH ---"
	ssh -p$(REMOTE_PORT) $(REMOTE_HOST) ' \
		set -e && \
		cd $(REMOTE_APP_PATH) && \
		echo "--- Extracting new application code ---" && \
		tar zxfv $(ARCHIVE_NAME) && \
		rm $(ARCHIVE_NAME) && \
		echo "--- Rebuilding and recreating services via orchestrator ---" && \
		cd $(REMOTE_DOCKER_PATH) && \
		docker compose -f $(REMOTE_DOCKER_COMPOSE_FILE) up -d --build --remove-orphans $(REMOTE_SOCCERTIME_SERVICE) && \
		echo "--- Fixing static volume permissions ---" && \
		docker run --rm -v $(REMOTE_STATIC_VOLUME):/data alpine chown -R $(DOCKER_UID):$(DOCKER_GID) /data && \
		echo "--- Applying database migrations ---" && \
		docker compose -f $(REMOTE_DOCKER_COMPOSE_FILE) exec -u $(DOCKER_UID):$(DOCKER_GID) $(REMOTE_SOCCERTIME_SERVICE) python manage.py migrate --noinput && \
		echo "--- Collecting static files ---" && \
		docker compose -f $(REMOTE_DOCKER_COMPOSE_FILE) exec -u $(DOCKER_UID):$(DOCKER_GID) $(REMOTE_SOCCERTIME_SERVICE) python manage.py collectstatic --noinput \
	'

# Target to clean up local temporary archive after upload
clean_local_archive:
	@echo "--- Cleaning up local archive ---"
	rm $(LOCAL_ARCHIVE_PATH)

# Target to upload files only without running deploy
upload-only: archive_app upload_files clean_local_archive
	@echo "Files uploaded successfully. No remote deployment executed."

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

# === Data Management (Docker volumes in production) ===

LOCAL_DB_PATH = ./db/db.sqlite3
LOCAL_CACHE_PATH = ./soccertime_data_cache.sqlite
LOCAL_MEDIA_PATH = ./media
BACKUP_SUFFIX = .backup.$(shell date +%Y%m%d_%H%M%S)

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
			chown $(DOCKER_UID):$(DOCKER_GID) /data/$(REMOTE_DB_FILE_IN_VOLUME) \
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
			chown $(DOCKER_UID):$(DOCKER_GID) /data/$(REMOTE_CACHE_FILE_IN_VOLUME) \
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
			chown -R $(DOCKER_UID):$(DOCKER_GID) /data \
		"; \
		rm -f /tmp/$(APP_NAME)-media.tgz \
	'
	@rm -f /tmp/$(APP_NAME)-media.tgz
	@echo "Media uploaded successfully."

.PHONY: help deploy-production archive_app upload_files remote_deploy clean_local_archive upload-only upload-config remote-restart download-db upload-db download-requests-cache upload-requests-cache download-media upload-media

# Default target: show help
.DEFAULT_GOAL := help

# Show help with all available commands
help:
	@echo "Soccertime - Deployment and management commands"
	@echo ""
	@echo "USAGE: make <target>"
	@echo ""
	@echo "DEPLOY:"
	@echo "  deploy-production    Full deploy (upload code + run on remote)"
	@echo "  upload-only          Upload code and configs without running deploy"
	@echo "  upload-config        Upload only configuration files"
	@echo "  remote-restart       Restart remote services without uploading"
	@echo ""
	@echo "DATABASE:"
	@echo "  download-db          Download database from server"
	@echo "  upload-db            Upload database to server"
	@echo ""
	@echo "REQUESTS CACHE:"
	@echo "  download-requests-cache  Download requests cache from server"
	@echo "  upload-requests-cache    Upload requests cache to server"
	@echo ""
	@echo "MEDIA (badges, flags):"
	@echo "  download-media       Download media directory from server"
	@echo "  upload-media         Upload media directory to server"
	@echo ""
	@echo "NOTE: All uploads/downloads create automatic backups before overwriting."

# Deployment configuration variables
# Loaded from .env file if available
-include .env
export

APP_NAME = soccertime

# Application archive to upload
ARCHIVE_NAME = $(APP_NAME).tgz
LOCAL_ARCHIVE_PATH = /tmp/$(ARCHIVE_NAME)

# Configuration files to upload
COMPOSE_PROD_FILE = compose.production.yaml
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
	@echo "--- Uploading application archive and configuration files ---"
	scp -P$(REMOTE_PORT) $(LOCAL_ARCHIVE_PATH) $(REMOTE_HOST):$(REMOTE_PATH)/
	scp -P$(REMOTE_PORT) $(COMPOSE_PROD_FILE) $(REMOTE_HOST):$(REMOTE_PATH)/
	@if [ -f "$(ENV_PROD_FILE)" ]; then \
		echo "Uploading $(ENV_PROD_FILE)..."; \
		scp -P$(REMOTE_PORT) $(ENV_PROD_FILE) $(REMOTE_HOST):$(REMOTE_PATH)/; \
	else \
		echo "Warning: $(ENV_PROD_FILE) not found locally. Skipping upload."; \
	fi

# Target to execute deployment commands on remote server via SSH
remote_deploy:
	@echo "--- Initiating remote deployment via SSH ---"
	ssh -p$(REMOTE_PORT) $(REMOTE_HOST) ' \
		set -e && \
		cd $(REMOTE_PATH) && \
		echo "--- Pulling latest Docker images ---" && \
		docker compose -f $(COMPOSE_PROD_FILE) pull nginx && \
		echo "--- Stopping and removing old services ---" && \
		docker compose -f $(COMPOSE_PROD_FILE) down --remove-orphans && \
		echo "--- Extracting new application code ---" && \
		tar zxfv $(ARCHIVE_NAME) && \
		rm $(ARCHIVE_NAME) && \
		echo "--- Copying compose file to compose.yaml ---" && \
		cp $(COMPOSE_PROD_FILE) compose.yaml && \
		echo "--- Bringing up new services ---" && \
		docker compose -f $(COMPOSE_PROD_FILE) up -d --build --remove-orphans && \
		echo "--- Applying database migrations ---" && \
		docker compose -f $(COMPOSE_PROD_FILE) exec web python -m manage migrate --noinput && \
		echo "--- Collecting static files ---" && \
		docker compose -f $(COMPOSE_PROD_FILE) exec web python -m manage collectstatic --noinput \
	'

# Target to clean up local temporary archive after upload
clean_local_archive:
	@echo "--- Cleaning up local archive ---"
	rm $(LOCAL_ARCHIVE_PATH)

# Target to upload files only without running deploy
upload-only: archive_app upload_files clean_local_archive
	@echo "Files uploaded successfully. No remote deployment executed."

# Target to upload only configuration files (without code)
upload-config:
	@echo "--- Uploading configuration files only ---"
	scp -P$(REMOTE_PORT) $(COMPOSE_PROD_FILE) $(REMOTE_HOST):$(REMOTE_PATH)/
	@if [ -f "$(ENV_PROD_FILE)" ]; then \
		echo "Uploading $(ENV_PROD_FILE)..."; \
		scp -P$(REMOTE_PORT) $(ENV_PROD_FILE) $(REMOTE_HOST):$(REMOTE_PATH)/; \
	else \
		echo "Warning: $(ENV_PROD_FILE) not found locally. Skipping upload."; \
	fi
	@echo "Configuration files uploaded successfully."

# Target to restart remote services without uploading
remote-restart:
	@echo "--- Restarting remote services ---"
	ssh -p$(REMOTE_PORT) $(REMOTE_HOST) ' \
		set -e; \
		cd $(REMOTE_PATH); \
		 \
		echo "--- Stopping services ---"; \
		docker compose -f $(COMPOSE_PROD_FILE) down --remove-orphans; \
		 \
		echo "--- Starting services ---"; \
		docker compose -f $(COMPOSE_PROD_FILE) up -d --remove-orphans; \
		 \
		echo "Services restarted successfully." \
	'

# === Database Management ===

# Data file paths
LOCAL_DB_PATH = ./db/db.sqlite3
REMOTE_DB_PATH = $(REMOTE_PATH)/db/db.sqlite3
LOCAL_CACHE_PATH = ./soccertime_data_cache.sqlite
REMOTE_CACHE_PATH = $(REMOTE_PATH)/soccertime_data_cache.sqlite
LOCAL_MEDIA_PATH = ./media
REMOTE_MEDIA_PATH = $(REMOTE_PATH)/media
BACKUP_SUFFIX = .backup.$(shell date +%Y%m%d_%H%M%S)

# Download database from server (with local backup)
download-db:
	@echo "--- Downloading database from remote ---"
	@if [ -f "$(LOCAL_DB_PATH)" ]; then \
		echo "Backing up local database to $(LOCAL_DB_PATH)$(BACKUP_SUFFIX)"; \
		cp $(LOCAL_DB_PATH) $(LOCAL_DB_PATH)$(BACKUP_SUFFIX); \
	fi
	scp -P$(REMOTE_PORT) $(REMOTE_HOST):$(REMOTE_DB_PATH) $(LOCAL_DB_PATH)
	@echo "Database downloaded successfully."

# Upload database to server (with remote backup)
upload-db:
	@echo "--- Uploading database to remote ---"
	@ssh -p$(REMOTE_PORT) $(REMOTE_HOST) ' \
		if [ -f "$(REMOTE_DB_PATH)" ]; then \
			echo "Backing up remote database"; \
			cp $(REMOTE_DB_PATH) $(REMOTE_DB_PATH).backup.$$(date +%Y%m%d_%H%M%S); \
		fi \
	'
	scp -P$(REMOTE_PORT) $(LOCAL_DB_PATH) $(REMOTE_HOST):$(REMOTE_DB_PATH)
	@echo "Database uploaded successfully."

# === Requests Cache Management ===

# Download cache from server (with local backup)
download-requests-cache:
	@echo "--- Downloading cache from remote ---"
	@if [ -f "$(LOCAL_CACHE_PATH)" ]; then \
		echo "Backing up local cache to $(LOCAL_CACHE_PATH)$(BACKUP_SUFFIX)"; \
		cp $(LOCAL_CACHE_PATH) $(LOCAL_CACHE_PATH)$(BACKUP_SUFFIX); \
	fi
	scp -P$(REMOTE_PORT) $(REMOTE_HOST):$(REMOTE_CACHE_PATH) $(LOCAL_CACHE_PATH)
	@echo "Cache downloaded successfully."

# Upload cache to server (with remote backup)
upload-requests-cache:
	@echo "--- Uploading cache to remote ---"
	@ssh -p$(REMOTE_PORT) $(REMOTE_HOST) ' \
		if [ -f "$(REMOTE_CACHE_PATH)" ]; then \
			echo "Backing up remote cache"; \
			cp $(REMOTE_CACHE_PATH) $(REMOTE_CACHE_PATH).backup.$$(date +%Y%m%d_%H%M%S); \
		fi \
	'
	scp -P$(REMOTE_PORT) $(LOCAL_CACHE_PATH) $(REMOTE_HOST):$(REMOTE_CACHE_PATH)
	@echo "Cache uploaded successfully."

# === Media Management (badges, flags) ===

# Download media directory from server (with local backup)
download-media:
	@echo "--- Downloading media from remote ---"
	@if [ -d "$(LOCAL_MEDIA_PATH)" ]; then \
		echo "Backing up local media to $(LOCAL_MEDIA_PATH)$(BACKUP_SUFFIX)"; \
		cp -r $(LOCAL_MEDIA_PATH) $(LOCAL_MEDIA_PATH)$(BACKUP_SUFFIX); \
	fi
	@mkdir -p $(LOCAL_MEDIA_PATH)
	rsync -avz -e "ssh -p$(REMOTE_PORT)" $(REMOTE_HOST):$(REMOTE_MEDIA_PATH)/ $(LOCAL_MEDIA_PATH)/
	@echo "Media downloaded successfully."

# Upload media directory to server (with remote backup)
upload-media:
	@echo "--- Uploading media to remote ---"
	@ssh -p$(REMOTE_PORT) $(REMOTE_HOST) ' \
		if [ -d "$(REMOTE_MEDIA_PATH)" ]; then \
			echo "Backing up remote media"; \
			cp -r $(REMOTE_MEDIA_PATH) $(REMOTE_MEDIA_PATH).backup.$$(date +%Y%m%d_%H%M%S); \
		fi \
	'
	rsync -avz -e "ssh -p$(REMOTE_PORT)" $(LOCAL_MEDIA_PATH)/ $(REMOTE_HOST):$(REMOTE_MEDIA_PATH)/
	@echo "Media uploaded successfully."
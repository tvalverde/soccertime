# Soccertime

Django application for tracking football results and statistics.

## Requirements

- [Docker](https://docs.docker.com/get-docker/)
- [Docker Compose](https://docs.docker.com/compose/install/)
- Make (optional, for using Makefile commands)

## Project structure

```
soccertime/
├── compose.yaml              # Docker Compose for development
├── compose.production.yaml   # Docker Compose for production
├── Dockerfile                # Application Docker image
├── Makefile                  # Deployment and management commands
├── nginx.conf                # Nginx configuration for production
├── .env.example              # Environment variables template
├── .env                      # Environment variables (development)
├── .env.production           # Environment variables (production)
├── soccertime/               # Django source code
├── templates/                # HTML templates
├── media/                    # Media files (badges, flags)
├── db/                       # SQLite database
└── soccertime_data_cache.sqlite  # HTTP requests cache
```

## Local development

### Initial setup

1. Clone the repository:

```bash
git clone <repository-url>
cd soccertime
```

2. Create the environment file:

```bash
cp .env.example .env
```

3. Start the application:

```bash
docker compose up -d --build
```

4. Apply migrations:

```bash
docker compose exec web python -m manage migrate
```

5. Access the application at http://localhost:8000

### Development commands

```bash
# Start services
docker compose up -d

# View logs
docker compose logs -f web

# Apply migrations
docker compose exec web python -m manage migrate

# Create migrations
docker compose exec web python -m manage makemigrations soccertime

# Create superuser
docker compose exec web python -m manage createsuperuser

# Collect static files
docker compose exec web python -m manage collectstatic --noinput

# Run data scraper
docker compose exec web python -m manage scrapit

# Stop services
docker compose down
```

## Production deployment

Deployment is done through the `Makefile` which automates the entire process.

### Prerequisites

- SSH access to the production server
- `.env.production` file configured locally
- Changes committed to git (deploy uses `git archive HEAD`)

### Available commands

```bash
# Show all available commands
make help
```

#### Deployment

| Command | Description |
|---------|-------------|
| `make deploy-production` | Full deployment (upload code + run on remote) |
| `make upload-only` | Upload code and configs without running deploy |
| `make upload-config` | Upload only configuration files |
| `make remote-restart` | Restart remote services without uploading code |

#### Database

| Command | Description |
|---------|-------------|
| `make download-db` | Download database from server |
| `make upload-db` | Upload database to server |

#### Requests cache

| Command | Description |
|---------|-------------|
| `make download-requests-cache` | Download requests cache from server |
| `make upload-requests-cache` | Upload requests cache to server |

#### Media (badges, flags)

| Command | Description |
|---------|-------------|
| `make download-media` | Download media directory from server |
| `make upload-media` | Upload media directory to server |

> **Note:** All upload/download commands create automatic backups before overwriting.

### Full deployment example

```bash
# 1. Make changes to the code
vim soccertime/views.py

# 2. Commit the changes (IMPORTANT: deploy uses git archive HEAD)
git add -p
git commit -m "feat: new feature"

# 3. Deploy to production
make deploy-production
```

Expected output:

```
--- Archiving application files ---
git archive --format=tgz -o /tmp/soccertime.tgz HEAD
--- Uploading application archive and configuration files ---
soccertime.tgz                                100%  150KB 1.2MB/s   00:00
compose.production.yaml                       100% 1882    50KB/s   00:00
.env.production                               100%  481    15KB/s   00:00
--- Initiating remote deployment via SSH ---
--- Pulling latest Docker images ---
--- Stopping and removing old services ---
--- Extracting new application code ---
--- Copying compose file to compose.yaml ---
--- Bringing up new services ---
--- Applying database migrations ---
--- Collecting static files ---
Deployment process completed successfully.
```

### Detailed deployment process

The `make deploy-production` command executes the following steps:

1. **archive_app**: Creates a `.tgz` archive of the code using `git archive HEAD`
2. **upload_files**: Uploads the archive, `compose.production.yaml` and `.env.production` to the server
3. **remote_deploy**:
   - Pulls the latest Nginx image
   - Stops current services
   - Extracts new code
   - Brings up services with `docker compose up -d --build`
   - Runs database migrations
   - Collects static files
4. **clean_local_archive**: Removes the local temporary archive

### Production architecture

In production, the application runs with:

- **Nginx**: Reverse proxy to serve static and media files
- **Uvicorn**: ASGI server for the Django application
- **Read-only containers**: For security, containers use `read_only: true` with `tmpfs` for temporary directories
- **Shared network**: Services communicate through an external Docker network (`shared_network`)

### Troubleshooting

#### Deployment fails with "Read-only file system"

Make sure `compose.production.yaml` has the `tmpfs` configured for the cache directory:

```yaml
tmpfs:
  - /tmp:size=50M,mode=1777
  - /var/tmp/soccertime_cache:size=50M,mode=1777
```

#### Changes are not reflected in production

The `git archive HEAD` command only includes committed changes. Verify your changes are in the commit:

```bash
# View uncommitted changes
git status

# Commit changes
git add <files>
git commit -m "description"

# Deploy again
make deploy-production
```

#### Container stuck on "Waiting"

This may indicate that the health check is failing. Connect to the server and check the logs:

```bash
ssh -p2200 user@hostname
cd docker/soccertime
docker compose -f compose.production.yaml logs web
```

## Environment variables

See `.env.example` for the complete list of available variables.

### Main variables

| Variable | Development | Production | Description |
|----------|-------------|------------|-------------|
| `DJANGO_DEBUG` | `true` | `false` | Debug mode |
| `DJANGO_CACHE` | `false` | `true` | Enable template caching |
| `DJANGO_ALLOWED_HOSTS` | `localhost` | `*` | Allowed hosts |
| `DJANGO_STATIC_URL` | `/static/` | `/soccertime/static/` | Static files URL |
| `DJANGO_FORCE_SCRIPT_NAME` | - | `/soccertime` | URL prefix |

## License

Private project.




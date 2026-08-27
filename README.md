# Soccertime

Django application for aggregating and displaying sports events (football, cycling, tennis, motorsports, and more) with TV channel information.

## Key Features

- **Automated Scraping:** Robust daily scraping from multiple sports sources with intelligent deduplication and updates.
- **Optimized Performance:** Aggressive N+1 query prevention using nested prefetching and view-level data pre-calculation.
- **Unified Visual Experience:** Consistent dark-themed UI across all event listings (favorites, daily agenda, sports, channels, and competitions).
- **Accessibility:** Accessible UI components with semantic HTML and ARIA labels.
- **Developer Friendly:** Clean architecture using polymorphism patterns (`child_event`) and standardized component structures.
- **REST API:** Everything the site shows, readable as JSON under `/api/v1/`, described by an OpenAPI document the code generates and browsable at `/api/v1/docs/`.

## Requirements

- [Docker](https://docs.docker.com/get-docker/)
- [Docker Compose](https://docs.docker.com/compose/install/)

## Project structure

```
soccertime/
├── compose.yaml              # Docker Compose for development
├── compose.production.yaml   # Docker Compose for production
├── Dockerfile                # Application Docker image
├── Makefile                  # Deployment and production operations (see `make help`)
├── CHANGELOG.md              # Project history and versioning
├── pyproject.toml            # Python project config (pytest, ruff, coverage)
├── requirements.txt          # Python dependencies (pinned versions)
├── .env.example              # Environment variables template
├── .env.production.local.example # Local production simulation env template
├── soccertime/               # Django application
│   ├── models.py             # Data models (Event, Match, Race, etc.)
│   ├── views.py              # View functions
│   ├── api/                  # Read-only REST API (DRF) and its OpenAPI schema
│   ├── admin.py              # Django admin configuration
│   ├── static/               # Static assets (CSS, JS)
│   ├── tests/                # Test suite (pytest)
│   ├── fixtures/             # Initial data fixtures (auto-loaded on fresh DB)
│   └── management/commands/  # Custom management commands
├── templates/                # HTML templates
├── media/                    # Media files (crests, flags)
└── db/                       # SQLite database
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
docker compose exec web python manage.py migrate
```

> **Note:** Initial fixtures (sports, competitions, teams, and favorites) are automatically loaded when migrations run on a fresh database.

5. Access the application at http://localhost:8000

### Development commands

```bash
# Start services
docker compose up -d

# View logs
docker compose logs -f web

# Apply migrations
docker compose exec web python manage.py migrate

# Create migrations
docker compose exec web python manage.py makemigrations soccertime

# Create superuser
docker compose exec web python manage.py createsuperuser

# Collect static files
docker compose exec web python manage.py collectstatic --noinput

# Run data scraper (Idempotent: updates existing records if details or time change slightly)
docker compose exec web python manage.py scrapit

# Run scraper (dry run - show events without saving)
docker compose exec web python manage.py scrapit --dry-run

# List available scraping sources
docker compose exec web python manage.py scrapit --list-sources

# Reset database (delete and recreate with fresh migrations + fixtures)
docker compose exec web python manage.py resetdb

# Stop services
docker compose down
```

### Initial fixtures

The application includes initial fixtures that are automatically loaded when migrations run on a fresh database:

- **Sports**: Fútbol, Automovilismo, Motociclismo, Baloncesto
- **Competitions**: La Liga EA Sports, Champions League, Fórmula 1, MotoGP
- **Teams**: FC Barcelona, CD Castellón, Barça Basket, FC Barcelona Femenino, Barcelona Atlétic
- **Favorites**: All teams and competitions above are automatically added as favorites

Fixture files are located in `soccertime/fixtures/`:
- `initial_data.json`: Sports, competitions, and teams
- `favorites.json`: Favorite teams and competitions

To manually load fixtures:

```bash
# Load all fixtures
docker compose exec web python manage.py loaddata initial_data favorites

# Load specific fixture
docker compose exec web python manage.py loaddata initial_data
```

### Database reset

For development purposes, you can reset the entire database:

```bash
# Interactive reset (asks for confirmation)
docker compose exec web python manage.py resetdb

# Non-interactive reset (no confirmation)
docker compose exec web python manage.py resetdb --noinput
```

This command will:
1. Delete the SQLite database file
2. Run all migrations to recreate the schema
3. Automatically load initial fixtures (via post_migrate signal)

### Testing

The project uses pytest with pytest-django for testing.

```bash
# Run all tests
docker compose exec web pytest

# Run tests with verbose output
docker compose exec web pytest -v

# Run tests with coverage report
docker compose exec web pytest --cov --cov-report=term-missing

# Run tests with HTML coverage report
docker compose exec web pytest --cov --cov-report=html
# Then open htmlcov/index.html in your browser

# Run specific test file
docker compose exec web pytest soccertime/tests/test_models.py

# Run specific test class
docker compose exec web pytest soccertime/tests/test_models.py::TestMatch

# Run tests excluding integration tests (faster)
docker compose exec web pytest -m "not integration"
```

### Linting & Formatting

The project uses [Ruff](https://docs.astral.sh/ruff/) for linting and code formatting.

```bash
# Check for linting errors
docker compose exec web ruff check soccertime/

# Fix auto-fixable linting errors
docker compose exec web ruff check soccertime/ --fix

# Format code
docker compose exec web ruff format soccertime/

# Check formatting without applying changes
docker compose exec web ruff format soccertime/ --check
```

## REST API

Everything the site shows is also readable as JSON, under `/api/v1/`. The API is
**read-only**: the only write the site accepts is the favourites cookie, which belongs to a
browser rather than to a caller, so every endpoint answers `405` to anything but a `GET`.
Nothing authenticates, exactly as the pages do not.

| Endpoint | What it lists |
| --- | --- |
| `/api/v1/events/` | Every event — matches, races and simple events in one chronological listing |
| `/api/v1/competitions/` | Competitions, with their sport, flag and how many events they still have |
| `/api/v1/sports/` | Sports, in the order the site groups them |
| `/api/v1/teams/` | Teams and their crests |
| `/api/v1/flags/` | Flags competitions are shown with |
| `/api/v1/channels/` | Channels, each with the links it carries |
| `/api/v1/channel-links/` | The link directory `/channels/` renders |
| `/api/v1/channel-link-sources/` | Where those links were imported from |
| `/api/v1/favorites/` | The owner's curated favourites |
| `/api/v1/schema/` | The OpenAPI 3 document, generated from the code (`?format=json` for JSON) |
| `/api/v1/docs/` | Swagger UI, served from this origin |

### Reading it

```bash
# What is on today, with something to watch it on
curl 'http://localhost:8000/api/v1/events/?today_onwards=true&watchable=true'

# One competition, newest first, fifty to a page
curl 'http://localhost:8000/api/v1/events/?competition=12&ordering=-date&page_size=50'

# What a search box would return
curl 'http://localhost:8000/api/v1/events/?search=real%20madrid'

# The owner's favourites, which is what the landing page shows
curl 'http://localhost:8000/api/v1/events/?favorites=true&upcoming=true'
```

Listings are paginated (`page`, `page_size`, 25 by default and 100 at most) and travel in a
`{count, next, previous, results}` envelope. Every filter a listing accepts is described in
the schema, because the same declaration is what applies it — see
`soccertime/api/filtering.py`. A parameter that cannot be read is refused with a `400` naming
it, rather than ignored.

Times are expressed in `Europe/Madrid`, with the offset attached, which is the clock the site
is read in. `is_favorite` and `watchable` mean exactly what the corresponding queryset
selects, so a client can draw the same stars and play buttons the pages do.

Reading is limited to 120 requests a minute per address by default
(`DJANGO_API_THROTTLE_RATE`); the counters need a cache, so the limit is inert in development.

## Local production simulation (Traefik + HTTPS)

This repository includes a local production-like stack in `compose.production.local.yaml`.

### Setup

1. Create the local production env file from template:

```bash
cp .env.production.local.example .env.production.local
```

2. Generate a local TLS certificate and private key for `mojon.local`:

```bash
mkdir -p .docker/traefik/certs
openssl req -x509 -nodes -newkey rsa:2048 \
  -keyout .docker/traefik/certs/mojon.local.key \
  -out .docker/traefik/certs/mojon.local.crt \
  -days 365 \
  -subj "/CN=mojon.local"
```

3. Start the local production stack:

```bash
make replica-up
```

4. Optionally map local hostnames in `/etc/hosts`:

```text
127.0.0.1 mojon.local traefik.mojon.local
```

> **Security note:** `.docker/traefik/certs/mojon.local.key` is intentionally ignored and must never be committed.

## Production deployment


The image is built by GitHub Actions and published to `ghcr.io/tvalverde/soccertime`, tagged
with the full commit hash. `make deploy-production` pulls the tag matching the commit being
deployed and retags it to `soccertime:latest` on the host, so the code no longer lives on the
server and what serves is the image whose checks passed.

The published package is public, so the server pulls it anonymously and holds no registry
credentials. Two files still travel with a deploy, both of them descriptions of how to run
the image on that machine rather than code: `.env.production`, which is deliberately not in
the repository — it holds the secret key — and therefore cannot be in a public image either,
and `compose.production.yaml`, which the server's own `~/docker/docker-compose.yml`
`include`s from the uploaded directory rather than defining itself.

`~/www/soccertime` on the server still holds the checkout the last archive-based deploy
unpacked there. Those two uploaded files live in that same directory and **must stay**: the
host's `docker-compose.yml` includes one and reads the other, and an `include` of a missing
file breaks every `docker compose` command on that machine, not only this service. What can
be cleared, once a release or two has gone out this way, is the unpacked code around them.

## Domain notes

### Channel links and sources

- `ChannelLink` usa ManyToMany con `ChannelLinkSource` para que un mismo enlace pertenezca a varias fuentes.
- `ChannelLinkSource`: campos `name` (único), `display_name` (por defecto al nombre), `enabled` (bool). Señales eliminan `ChannelLink` huérfanos al borrar la última source.
- Comando unificado: `docker compose exec web python -m manage addlinksource --source <newera|elcano> --file <path> [--dry]`
  - **Soporte de fuentes:**
    - `newera`: Formato de texto con bloques de 2 líneas (Nombre --> Subcat / Link).
    - `elcano`: Formato de texto estructurado por secciones (`=== CATEGORIA ===`).
  - **Estrategias de Matching:**
    - Normalización de nombres (`fix_name`) para mapear variantes (ej: "Movistar" -> "M+").
    - Extracción inteligente de calidad (SD, HD, FHD, UHD, 1080p, 720p).
    - Lógica de seguridad para nombres cortos (evita falsos positivos como "La" -> "LaLiga").
    - Filtro Anti-Horeca: Evita asociar enlaces residenciales a canales de bares/restaurantes salvo que el enlace lo especifique.
- Admin: `ChannelLinkSource` registrado; en `ChannelLink` puedes filtrar/buscar/seleccionar sources.




### Prerequisites

- SSH access to the production server
- `.env.production` file configured locally
- The commit pushed to `main` and its CI run green, so the image exists to be pulled

### Available commands

```bash
# Show all available commands
make help
```

#### Deployment

| Command | Description |
|---------|-------------|
| `make deploy-production` | Full deployment (pull the published image + snapshot the database + hand over) |
| `make upload-config` | Upload only `.env.production` |
| `make upload-compose` | Upload the service definition of the commit being deployed |
| `make remote-restart` | Recreate remote services without deploying |
| `make remote-scrape` | Run the scraper on the server and clear the cache |
| `make remote-check` | Run Django's deployment checks against production |
| `make remote-smoke-test` | Verify a live deploy from outside: health plus every public page |
| `make remote-clear-cache` | Drop the rendered page cache |
| `make remote-redownload-images` | Restore flag images missing from the media volume |

> **Note:** `deploy-production` ends with `remote-smoke-test`, so a deploy that leaves
> the site broken fails instead of reporting success. It waits for the container to
> report `healthy` and then fetches the public pages **from outside the server** — an
> unhealthy container is dropped from the proxy's routing table, so the application
> can answer 200 on localhost while every visitor gets a 404. Override the checked
> pages with `SMOKE_PATHS` and the entry point with `PRODUCTION_URL`.

> **Note:** pages are cached for an hour, so a fix is not visible until
> `make remote-clear-cache` runs (or the cache expires).

#### Database

| Command | Description |
|---------|-------------|
| `make backup-remote-db` | Snapshot the database to the host, compressed (~5.5 MB) |
| `make backup-remote-media` | Snapshot the media volume to the host (~2 MB compressed) |
| `make pull-remote-backups` | Copy the remote snapshots into `./backups` |
| `make list-remote-backups` | List the database and media snapshots kept |
| `make restore-remote-db BACKUP=<file>` | Restore a snapshot and restart the service |
| `make download-db` | Download database from server |
| `make upload-db` | Upload database to server |

> **Note:** `deploy-production` snapshots the database and the media automatically
> before applying migrations, so there is always a rollback point.
>
> Snapshots are kept **on the host**, not inside the volumes they protect, and are
> retained generationally: the last `KEEP_LAST` (3), one per day for `KEEP_DAILY`
> days (7) and one per month for `KEEP_MONTHLY` months (12). A plain count would
> measure history in deploys instead of in time — a busy afternoon once evicted a
> five-month-old restore point, which is exactly what was needed to investigate a
> data problem that had gone unnoticed for months. The ceiling is around 22 copies
> at ~7.5 MB each.
>
> The database snapshot uses SQLite's backup API rather than copying the file, since
> a byte-for-byte copy of a live database can capture a half-written transaction.
>
> Everything still lives on one machine, so `make pull-remote-backups` copies the
> snapshots here. Flags can also be re-fetched with `make remote-redownload-images`,
> since each stores its source URL, but a team crest does not: it only returns when
> that team is scraped again, which is what the media snapshot preserves.

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

# 2. Commit and push: the image is built from what is on `main`
git add -p
git commit -m "feat: new feature"
git push

# 3. Wait for the checks and the publish job
gh run watch

# 4. Deploy to production
make deploy-production
```

### Detailed deployment process

`make deploy-production` runs these steps, in this order:

1. **pull_image**: fetches `ghcr.io/tvalverde/soccertime:sha-$(git rev-parse HEAD)` on the
   server. It comes first because it is the step most likely to fail — the commit may not be
   published yet — and nothing on the server has changed when it does.
2. **upload-compose** and **upload-config**: send the two files the image cannot carry —
   `compose.production.yaml`, read out of git at the commit being deployed, and
   `.env.production` from the working copy, which is where that file lives.
3. **backup-remote-db** and **backup-remote-media**: snapshots taken before anything migrates.
4. **remote_deploy**: retags the outgoing image as `soccertime:previous`, puts the pulled one
   under `soccertime:latest` and drops the registry name, then — in throwaway containers, with
   the previous container still serving — runs `check --deploy --fail-level WARNING`,
   `collectstatic` and `migrate`, and finally hands the service over with `scripts/relay.sh`.
5. **remote-smoke-test**: fetches the public pages from outside, so a deploy that leaves the
   site broken fails instead of reporting success.
6. **prune-remote-images**: drops superseded images of this project, keeping `:previous`.

Rolling back is either of two things: `soccertime:previous` is still on the host, and any
commit CI ever published can be deployed by name with
`make deploy-production DEPLOY_TAG=sha-<commit>`.

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

The image is built from what was pushed, so a change that is only committed locally — or one
whose CI run has not finished — is not in the image the deploy asks for. The pull fails by
name rather than deploying something older:

```bash
git status          # anything uncommitted is not in the image
git push
gh run watch        # the publish job runs after the checks pass
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
| `DJANGO_SECRET_KEY` | (auto-generated) | **required** | Secret key for cryptographic signing |
| `DJANGO_DEBUG` | `true` | `false` | Debug mode |
| `DJANGO_CACHE` | `false` | `true` | Enable template caching |
| `DJANGO_ALLOWED_HOSTS` | `localhost` | `*` | Allowed hosts |
| `DJANGO_STATIC_URL` | `/static/` | `/static/` | Static files URL |
| `DJANGO_FORCE_SCRIPT_NAME` | - | (optional) | URL prefix (only when intentionally serving under a subpath) |
| `DOCKER_UID` | `1000` | `1000` | User ID for application and database files |
| `DOCKER_GID` | `1000` | `1000` | Group ID for application and database files |

### Transport security

Off by default so local development keeps working over plain HTTP.

| Variable | Development | Production | Description |
|----------|-------------|------------|-------------|
| `DJANGO_BEHIND_TLS_PROXY` | `false` | `true` | Trust `X-Forwarded-Proto`, so Django knows the proxied request is HTTPS |
| `DJANGO_SECURE_COOKIES` | `false` | `true` | Mark the session and CSRF cookies as `Secure` |
| `DJANGO_SECURE_SSL_REDIRECT` | `false` | `true` | Redirect `http://` inside Django. Requires `DJANGO_BEHIND_TLS_PROXY`, otherwise Django never sees a request as secure and redirects it to itself forever |
| `DJANGO_SECURE_HSTS_SECONDS` | `0` | `31536000` | HSTS lifetime. Browsers remember it: a visitor that receives the header refuses plain HTTP for the whole period even after the header is removed |
| `DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS` | `false` | `false` | Extends HSTS to every subdomain. Deliberately off |
| `DJANGO_SECURE_HSTS_PRELOAD` | `false` | `false` | Submits the domain to the browser preload lists. Deliberately off: leaving them takes months |

`manage.py check --deploy` must come back clean; `make remote-check` runs it against
production. Two checks are silenced on purpose in `settings.py` (`W005` and `W021`),
because `includeSubDomains` and `preload` are policy decisions rather than defects.

`healthz` is exempt from the SSL redirect via `SECURE_REDIRECT_EXEMPT`: the container
health check reaches the app directly over plain HTTP, and redirecting it makes the
check fail, which takes the service out of the proxy's routing table.

### Generating a secret key

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

## License

Private project.




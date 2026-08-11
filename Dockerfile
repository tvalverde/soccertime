# syntax=docker/dockerfile:1
FROM python:3-alpine
# What lets the deploy prune this project's superseded images without touching the ones
# other services on the host built and cannot re-pull.
LABEL org.opencontainers.image.title="soccertime"
ARG DOCKER_UID=1000
ARG DOCKER_GID=1000
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
RUN python -m venv /venv
ENV VIRTUAL_ENV=/venv
ENV PATH="/venv/bin:$PATH"
RUN adduser -D -H -u ${DOCKER_UID} appuser
WORKDIR /code
COPY  --chown=appuser:appuser  requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY --chown=appuser:appuser . .
USER appuser
# The image defaults to what is safe when nothing overrides it, and development opts in
# through its own `.env` — which sets every one of these explicitly, as does
# `.env.production`, so flipping them changes neither environment. What changes is the day
# an entry goes missing from a file that is deliberately not in the repository: the
# container used to come up in debug mode, serving stack traces and settings to anyone, and
# with no `DJANGO_SECRET_KEY` it fell back to the hardcoded development one. Now it has no
# key and no debug, so it refuses to start: the health check fails, the proxy withdraws the
# route, and the site answers 404 rather than handing out its own configuration.
ENV DJANGO_DEBUG=false \
    DJANGO_CACHE=false \
    DJANGO_ADMIN_ENABLED=false \
    DJANGO_USE_X_FORWARDED_HOST=false \
    DJANGO_SESSION_COOKIE_PATH=/ \
    DJANGO_DATABASE_DEFAULT_NAME=/code/db/db.sqlite3 \
    REQUESTS_CACHE=/code/db/soccertime_data_cache

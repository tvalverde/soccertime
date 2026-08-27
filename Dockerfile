# syntax=docker/dockerfile:1
# The version this tag already resolved to, written down. `python:3-alpine` picks whatever
# the newest interpreter is at the moment of each build, on whichever machine builds it —
# so the site could change interpreter without a line of this repository changing, and two
# builds of the same commit were never the same image. It is also the number CI installs on
# its runner (`test_ci_workflow.py` reads it from here), which cannot be decided by a tag
# that moves.
FROM python:3.14-alpine
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
# Development and production share this image, so the toolchain cannot simply be deleted:
# `make test`, `make lint` and `make typecheck` all run inside a container built from here.
# It is installed on request instead, and a build that says nothing is a production build.
# Neither direction can go wrong quietly — a development image built without the flag fails
# on the first `pytest`, and a production image cannot pick it up by accident.
ARG INSTALL_DEV=false
COPY  --chown=appuser:appuser  requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements.txt && \
    if [ "$INSTALL_DEV" = "true" ]; then pip install --no-cache-dir -r requirements-dev.txt; fi
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

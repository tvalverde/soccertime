# syntax=docker/dockerfile:1
FROM python:3-alpine
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
RUN python -m venv /venv
ENV VIRTUAL_ENV=/venv
ENV PATH="/venv/bin:$PATH"
RUN adduser -D -H -u 1000 appuser
WORKDIR /code
COPY  --chown=appuser:appuser  requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY --chown=appuser:appuser . .
USER appuser
ENV DJANGO_DEBUG=true \
    DJANGO_CACHE=false \
    DJANGO_ADMIN_ENABLED=true \
    DJANGO_USE_X_FORWARDED_HOST=false \
    DJANGO_SESSION_COOKIE_PATH=/ \
    DJANGO_DATABASE_DEFAULT_NAME=/code/db/db.sqlite3 \
    REQUESTS_CACHE=/code/cache/soccertime_data_cache.sqlite

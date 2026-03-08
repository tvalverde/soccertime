# Soccertime Onboarding Guide

This document provides the necessary context for understanding and working on the Soccertime project.

## 1. Project Context & Persona

-   **What is it?** A personal Django application to aggregate and display sports events (football, cycling, tennis, etc.) along with their TV channel information.
-   **Architecture:** It's a monolithic Django application designed to run entirely within Docker containers.
-   **Persona:** The application is built for a small, private group of users (the author and their relatives). The primary goal is usability and reliability for this group, not large-scale public use.

## 2. Standards & Architecture

-   **Technology Stack:**
    -   **Backend:** Python / Django
    -   **Database:** SQLite (for both development and production)
    -   **Containerization:** Docker and Docker Compose
    -   **Production Server:** Uvicorn (with Nginx as a reverse proxy)
    -   **Code Style & Linting:** The project uses [Ruff](https://docs.astral.sh/ruff/) for all code formatting and linting. Configuration is located in `pyproject.toml`. Before committing, always run `ruff format .` and `ruff check . --fix`.
    -   **Changelog:** Maintain the `CHANGELOG.md` file. Document all notable changes (Added, Changed, Deprecated, Removed, Fixed, Security) after every modification, following the [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) standard.
    -   **Testing:** The project uses `pytest` and `pytest-django`. All new features or bug fixes should be accompanied by tests.
    -   Tests are located in the `soccertime/tests/` directory.
    -   Run the full test suite with: `docker compose exec web pytest`

## 3. Workflow & Commands

-   **Local Development Setup:**
    1.  Create the environment file from the template if it does not already exist: `[ -f .env ] || cp .env.example .env`
    2.  Build and start the services: `docker compose up -d --build`
    3.  Apply database migrations: `docker compose exec web python manage.py migrate`
    4.  Access the app at `http://localhost:8000`.

-   **Key Management Commands:**
    -   `docker compose exec web python manage.py scrapit`: This is the core command for fetching event data. It is run automatically as a daily cron job in production to keep the schedule updated.
    -   `docker compose exec web python manage.py addlinksource --source <name> --file <path>`: This command is used to manually update the TV channel links from a local text file.
    -   `docker compose exec web python manage.py resetdb`: Resets the database (deletes and recreates with migrations + fixtures). Useful for development.

-   **Production Deployment:**
    -   **Status:** **To Be Defined (TBD)**.
    -   **Note:** The previous deployment method using the `Makefile` is considered deprecated.
    -   **Future Direction:** The new workflow will be based on building and deploying a production-ready Docker image of the application. The specific steps for this process (e.g., CI/CD pipeline, registry pushes) will be discussed and defined separately.

## 4. Guardrails & Knowledge

-   **Configuration:** The application is configured exclusively through environment variables. The `.env.example` file serves as a template, and `.env.production.local.example` is the template for local production simulation. **Never commit secrets or environment files to the repository.**
-   **Data Source:** The application is highly dependent on the external websites targeted by the `scrapit` command. Changes to these websites can break the data flow.
-   **Database:** As the project uses SQLite, be mindful that complex schema changes and data migrations should be handled with care.
-   **External Data Files:** Files used as input for `addlinksource` (like `elcano.txt` or `newera.txt`) are considered external data sources and are **not** part of the git repository. Do not commit them.
-   **Local TLS Key Material:** For local production simulation with Traefik, generate `.docker/traefik/certs/mojon.local.key` locally. This private key file must never be committed; only non-sensitive templates/configuration should be tracked.
-   **Initial Fixtures:** The application includes initial fixtures (`soccertime/fixtures/`) that are automatically loaded via a `post_migrate` signal when the database is empty. These include basic sports, competitions (La Liga, Champions League, Fórmula 1, MotoGP), teams (FC Barcelona, CD Castellón, Barça Basket, etc.), and their corresponding favorites. Fixtures use sequential PKs starting from 1.

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
    -   **Changelog:** Document all notable changes (Added, Changed, Deprecated, Removed, Fixed, Security) after every modification, following the [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) standard. **There are two, and they are not interchangeable:** `CHANGELOG.md` is the website and its API; `android/CHANGELOG.md` is the two applications. They release on separate tags — `v*` and `android-v*` — so an entry in the wrong file is filed under a release its reader will never install.
    -   **Testing:** The project uses `pytest` and `pytest-django`. All new features or bug fixes should be accompanied by tests.
    -   **Regression Testing:** Always create a regression test when fixing a bug to prevent it from reappearing in the future.
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
    -   Execute `make deploy-production` to deploy the application to the production server.
    -   The image is built by GitHub Actions and published to `ghcr.io/tvalverde/soccertime`,
        and the deploy pulls the tag of the commit being deployed. **A commit that is not
        pushed, or whose CI run is not green, cannot be deployed**: the pull fails by name,
        before anything on the server has changed. The only files still uploaded are
        `.env.production` and `compose.production.yaml`, which describe how to run the image
        there. Roll back with `soccertime:previous` on the host or
        `make deploy-production DEPLOY_TAG=sha-<commit>`.

## 4. Guardrails & Knowledge

-   **Configuration:** The application is configured exclusively through environment variables. The `.env.example` file serves as a template, and `.env.production.local.example` is the template for local production simulation. **Never commit secrets or environment files to the repository.**
-   **Data Source:** The application is highly dependent on the external websites targeted by the `scrapit` command. Changes to these websites can break the data flow.
-   **Database:** As the project uses SQLite, be mindful that complex schema changes and data migrations should be handled with care. It runs in **WAL mode**, so the database is two files: the newest commits live in `db.sqlite3-wal` until a checkpoint folds them in. Anything that copies, moves or replaces it must go through a connection (`python -m soccertime.backups snapshot-db`) and must delete the `-wal`/`-shm` of the database it replaces, with the service stopped. `test_database_transport.py` enforces both rules against the `Makefile`.
-   **External Data Files:** Files used as input for `addlinksource` (like `elcano.txt` or `newera.txt`) are considered external data sources and are **not** part of the git repository. Do not commit them.
-   **Local TLS Key Material:** For local production simulation with Traefik, generate `.docker/traefik/certs/mojon.local.key` locally. This private key file must never be committed; only non-sensitive templates/configuration should be tracked.
-   **Initial Fixtures:** The application includes initial fixtures (`soccertime/fixtures/`) that are automatically loaded via a `post_migrate` signal when the database is empty. These include basic sports, competitions (La Liga, Champions League, Fórmula 1, MotoGP), teams (FC Barcelona, CD Castellón, Barça Basket, etc.), and their corresponding favorites. Fixtures use sequential PKs starting from 1.

## 5. Development Best Practices & Patterns

-   **Performance (N+1 Avoidance):**
    -   Always use `.select_related()` for ForeignKey relationships and `.prefetch_related()` for ManyToMany or reverse relationships in Views.
    -   When rendering lists of channels/links in templates, use the `EventQuerySet.with_related()` method which performs nested prefetching.
    -   In templates, use `{% with %}` blocks to cache expensive property calls or methods that are used multiple times (e.g., `channel.enabled_links`).
-   **Model Architecture:**
    -   **Polymorphism:** Use the `Event.child_event` property to access specific event instances (`Match`, `Race`, `SimpleEvent`) instead of using complex `if/elif` chains in templates.
    -   **Multi-table inheritance:** `Match`, `Race` and `SimpleEvent` each have their own table joined to `soccertime_event`, so reading one always costs a join. Do not try to remove it without profiling first: `with_related()` already makes the child share the parent's caches, measured at **0 extra queries** across 25 events on the production database.
    -   **In-Memory Filtering:** Properties that filter related sets (like `Channel.enabled_links`) should use list comprehensions over `self.links.all()` to leverage Django's prefetch cache instead of hitting the DB with `.filter()`.
-   **REST API (`soccertime/api/`):**
    -   It is **read-only**, and stays that way: the site's only write is the favourites
        cookie, which is signed for a browser and cannot be authorised by an API caller.
    -   A query parameter is declared once, as a `QueryFilter` in `filtering.py`, and used
        twice: to narrow the queryset and to document itself in the schema. Never filter
        inside `get_queryset` without declaring it there — an undocumented parameter cannot
        be used by anybody.
    -   Serializers must never read an image file. The dimensions come from the row, for the
        same reason the model fields do not declare `width_field` / `height_field`.
    -   Fields that mirror a queryset (`is_favorite`, `watchable`) are pinned against it row
        by row in `test_api_events.py`. Change one and the test will tell you about the other.
    -   Do not use drf-spectacular's own Swagger view: it loads the library from a CDN and
        starts it from an inline script, and the CSP here allows neither.

-   **Template & UI Standardization:**
    -   **Unified Rendering:** `agenda.html` is the reference template for all event listings. Do not create new listing templates unless strictly necessary.
    -   **Component Consistency:**
        -   **Competitions:** Always show with their flag (`{{ competition.flag|render_image_markup }}`). All image markup comes from that filter, backed by `soccertime/rendering.py`; models hold the image and its dimensions, never the HTML.
        -   **Teams:** Always show as `[Crest] + Name` to avoid ambiguity between teams sharing the same crest (e.g., Male/Female categories).
    -   **Empty States:** Pass `empty_message` / `empty_message_level` in the view context (see `empty_state()` in `views.py`) and include `soccertime/empty_state.html` when the listing is empty. Do **not** use the Django `messages` framework here: the listing views are wrapped in `@cache_page`, so a per-request message is stored in the shared page cache and served to every other visitor.
    -   **Accessibility:** Always provide `aria-label` for links and interactive elements, especially those containing only icons or images.

## 6. The Android Apps (`android/`)

Two native applications that read the same public API the site serves, living beside the
Django project rather than in a repository of their own. They share this repository and
nothing else: the image built from here runs Django, and `.dockerignore` refuses `android/`
so `COPY . .` never carries it.

-   **Layout.** One Gradle build, three modules. `:core` is everything that is not a screen —
    the API client, the data layer, the time arithmetic and the view models — and both
    applications are thin over it, so the phone and the television disagree about
    presentation and about nothing else. `:app-mobile` is `es.mojon.soccertime`,
    `:app-tv` is `es.mojon.soccertime.tv`; the application ids differ so both install on one
    device. The TV activity is registered under `LEANBACK_LAUNCHER`, which is the only
    category the Fire TV home screen lists.
-   **Versions.** `android/gradle/libs.versions.toml` is the single place a version is
    written, and it is the manifest the `gradle` entry in `.github/dependabot.yml` watches.
    `soccertime/tests/test_dependency_updates.py` derives its expectation from the files
    actually present, so a new kind of manifest and its Dependabot entry have to arrive in
    the same commit.
-   **AGP 9 compiles Kotlin itself.** Applying `org.jetbrains.kotlin.android` is no longer
    redundant, it is a hard configuration error — the plugin refuses and the build never
    reaches a module. Only the Compose and serialization compiler plugins are still applied
    on their own; built-in Kotlin replaces the base Android Kotlin plugin and nothing else.
    AGP pulls in an older Kotlin than the catalog names, so the root `build.gradle.kts` puts
    `kotlin-gradle-plugin` on the buildscript classpath purely to raise it: without that pin
    the apps compile with AGP's bundled version rather than the one Dependabot is watching.
-   **`minSdk` is 25 and that is the whole point.** The Fire TV Stick 4K runs Fire OS 6 on
    Android 7.1, where `java.time` does not exist; every instant this app handles arrives as
    an ISO-8601 string with an offset, and it is core library desugaring that makes
    `OffsetDateTime` available down there rather than a second date library.
-   **Never delete the certificates in `core/src/main/res/raw/`.** `www.mojon.es` presents a
    Let's Encrypt chain that anchors at ISRG Root X1 — today by way of Root YR cross-signed
    from it — and an Android 7.1 trust store may not carry either. It is Amazon's store on
    that hardware, not Google's, and "may" is not something a release is built on. Both
    generations are bundled through `network_security_config.xml`, which is declared in
    `:core`'s manifest so neither application can ship having forgotten it. There is no
    fallback to fail over to: the site sends HSTS and redirects `http`, so a failed handshake
    is a blank app rather than a degraded one.
-   **Commands.** `make android-build`, `android-test`, `android-lint`, `android-release`,
    `android-install-mobile`, and `android-install-tv ADB_HOST=<address>`. Gradle runs on the
    host against a JDK and an Android SDK, not inside the `web` container.
-   **Some things only the hardware can answer.** Whether the handshake succeeds on Android
    7.1, whether anything on the device answers an `acestream://` intent, and whether every
    control can be reached with a D-pad are invisible to the unit suite and to an emulator.
    Sideload and look before believing any of the three. The apps never require a particular
    player: a link is fired as a plain `ACTION_VIEW` and the system decides who answers it —
    no install check, no `<queries>` block, and no third-party app is ever named.
-   **Releases** are cut by tagging `android-v<version>`, which is what
    `.github/workflows/android-release.yml` runs on. It refuses to publish anything it cannot
    verify: a missing secret stops the run rather than producing an unsigned APK, and
    `apksigner verify --min-sdk-version 25` is run on both before the release is created.
    The tag and the `versionName` in both modules must agree, and the workflow checks that too.
-   **The signing key exists for one reason: updating without uninstalling.** Android refuses
    to install a version signed with a different key, and uninstalling takes the favourites
    with it, because they live on the device and nowhere else. Made once, never committed,
    kept somewhere with a backup — losing it means no installed copy can ever be updated again:

    ```
    keytool -genkeypair -v -keystore soccertime-release.jks -alias soccertime \
      -keyalg RSA -keysize 4096 -validity 10000 -storetype PKCS12
    base64 -w0 soccertime-release.jks   # the value of ANDROID_KEYSTORE_B64
    ```

    Three repository secrets: `ANDROID_KEYSTORE_B64`, `ANDROID_KEYSTORE_PASSWORD` and
    `ANDROID_KEY_ALIAS`. There is a fourth, `ANDROID_KEY_PASSWORD`, and it is optional because
    **a PKCS12 keystore has one password** — `keytool` refuses to set two ("Different store and
    key passwords not supported for PKCS12 KeyStores") and ignores the second, so the key's
    password *is* the store's. The build falls back to it rather than failing a release with an
    authentication error nobody would expect.

    The same variables work locally, which is all `make android-release` needs; without them
    `assembleRelease` still builds, unsigned, which is what makes it a check anybody can run
    against R8.
-   Everything in section 2 applies here unchanged: English in all source and comments,
    Conventional Commits, tests with every change, and a changelog entry — which for anything
    under `android/` means **`android/CHANGELOG.md`**, not the one at the root.

## 7. Language & Localization

-   **Conversations:** All chat conversations and explanations must be conducted in Castilian Spanish.
-   **Code & Technical Artifacts:** All source code, in-code comments, documentation, commit messages, configuration files, and tests must be written strictly in English.

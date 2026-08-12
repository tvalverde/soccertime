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

### Code review of 2026-08-11/12 (106 commits, reviewed 2026-08-12)

Findings from reviewing every change since `1e70080`, ordered by criticality. Each was
verified — reproduced in the replica, measured against the data, or proven from the code —
before being written down; the two worst were both confirmed by demonstration.

- [ ] **Validate the reconciliation's removals over several days** — for the assistant to
  run, started 2026-08-13. The presence reconciliation shipped in 0.5.1 removes a future
  event after two consecutive successful scrapes stop listing it. The healthy signature is
  small `first_miss` counts that reset on the next pass and near-zero
  `removed_after_2_misses`; the failure signature is a sport steadily accumulating removals,
  which would mean one of the source's pages does not list its own coverage stably — the
  exact fissure the two-miss grace exists to absorb, and the one thing the design could not
  measure in advance. Check on 3–4 different days:

  1. Per sport and per day: totals of `superseded`, `first_miss`, `removed_after_2_misses`.
  2. For the rows sitting at `missing_scrapes>0` (tomorrow's potential removals, and the
     only ones that can be checked before they vanish): is the pairing listed elsewhere
     (moved — fine), gone from the live page (cancelled/de-listed — fine), or **still on
     the live page** (wrongly pruned — the bug this validation exists to catch)?
  3. Cross-check volume: future-event count per sport should not drift downward without the
     stats explaining it.

  **How to actually read the numbers — the original note here was wrong twice.** The
  `Reconciled:` lines never reach `docker compose logs`: the cron runs `scrapit` through
  `docker compose exec`, whose stdout goes to the caller, and the crontab appends it to
  `~/scrapit.log` on the host — so `grep Reconciled ~/scrapit.log` there, not
  `make remote-logs`. And the scrape is **every 4 hours** (`4 */4 * * *`), not hourly, so a
  first_miss becomes a removal in 8 hours, not 2. That file does not rotate; it has held
  every run since February.

  **Day 1 (2026-08-13, pass run at 00:30 UTC):**
  - Runs 2026-08-12 16:04 / 20:04 and 2026-08-13 00:04. At 16:04 — the first run with two
    misses accumulable — the backlog cleared: Fútbol removed=3, Tenis removed=4, Ciclismo
    removed=4. At 20:04: Fútbol first_miss=1, Ciclismo superseded=2, no removals. At
    00:04: nothing to report at all, every counter zero.
  - The one row at `missing_scrapes=1`: a friendly, Valencia-Mestalla – Teruel, 20:30
    local, de-listed by the source 26 minutes before kick-off. The grace held — one miss,
    not removed — and the event then started, ageing out of the candidate window. Exactly
    the behaviour the two-miss design promised.
  - Volume, replica snapshot of 12th 18:00 → production 13th 00:30: Baloncesto 763=763,
    Fútbol 755→758, Tenis 288=288, Ciclismo 146→147, Motociclismo 144=144, Automovilismo
    85=85, Golf 11=11. No downward drift; total future 2,196 against 2,148 on the 11th.
  - **Verdict so far: healthy.** One limitation found: the log records *counts*, not which
    events were removed, so the 11 removals of the 16:04 run can never be audited against
    the live page. If a later pass shows a sport accumulating removals, the first move is
    to make `scrapit` name what it deletes.

  If a page turns out to list unstably, the options already considered: raise
  `MISSES_BEFORE_REMOVAL` for that unit kind, or narrow that unit's declared coverage.
  Record the verdict here either way, with the numbers.

### Improvements

Ordered by the utility each would add, judged against the site and its data on 2026-08-11.
Every number below is a measurement taken that day, not an estimate, so the case for each can
be re-read rather than re-argued. None has been designed beyond what is written here — except
the last, which is a different kind of thing and says so.

- [ ] **A shared link says nothing about itself.** No `og:title`, no `og:image`, no
  `twitter:card`, no JSON-LD, no canonical, no sitemap — checked against the live response.
  This is a site people paste into WhatsApp and Telegram, and those links arrive bare. The
  same change covers discovery: futbolenlatv marks its fixtures up with schema.org, which is
  how sports listings reach Google's results at all. Cheap, and the returns are not subtle.

- [ ] **It looks like an app and cannot be installed.** Bottom navigation, mobile-first
  layout, and no `manifest` and no `apple-touch-icon`. Nobody can add it to a home screen,
  which is precisely how something like this gets used: open, check what is on, close.

- [ ] **The big pages are heavy for a phone — the transfer half is done, the rendering half
  remains.** Responses are gzip-compressed since 2026-08-13: `/competitions/` now travels at
  **28 KB instead of 338** and `/channels/` at **11 KB instead of 186**, measured against
  production data, with a test pinning that a browser asking for gzip still gets its empty
  304 on revalidation. What compression does not fix: `/channels/` still renders all 381
  links in one page, and a phone still parses the full 338 KB of `/competitions/` markup.
  That part is purely how much is rendered in one go, and it is what is left of this entry.

- [ ] **Nothing reports the system's own health, and the database is 96% past.** **49,985 past
  events against 2,148 future ones**, with nothing that purges them: unbounded growth of rows
  nobody will ever read. And if the scrape broke at three in the morning the agenda would
  empty out, with nothing to say so until somebody noticed. Same family, and the monitoring
  half is already designed inside the parked entry below.

- [ ] **On a phone, the channel column sits past the horizontal scroll.** Surfaced by the
  channel-visibility work of 2026-08-11 and parked since: the column now names the channel
  for every event, but on a phone it is off-screen until the table is scrolled sideways, so
  the gain is a desktop one until the mobile layout is revisited. Cosmetics by the criteria
  above, which is why it sits here.

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

- [ ] **Production's proxy floats and the replica's is pinned.** The server runs
  `traefik:latest`, today 3.7.10; `compose.production.local.yaml` names an exact version so
  the replica rehearses the real thing. That pin has to be updated by hand when the server
  pulls a newer Traefik, and nothing notices if it is not — which is exactly how a deploy
  measured at 0.2s locally cost 13s in production on 2026-08-12. Either pin the server too,
  or have `make remote-ps` compare the two and say so.

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

An index only: one line per item, newest first. The detail — measurements, rejected
alternatives, the story of each — is in `CHANGELOG.md` under the version that shipped it,
and in the git history. This section held full paragraphs until 2026-08-13; they
duplicated the changelog and were compressed into what an index is for: finding things.

- **Responses are compressed** (0.8.0, 2026-08-13) — `/competitions/` travels at 28 KB
  instead of 338; a test pins that revalidation still answers an empty 304.
- **The `[project]` table left `pyproject.toml`** (0.8.0, 2026-08-13) — its version said
  0.3.0 four releases after v0.7.0, and nothing read it.
- **Favourites belong to the visitor** (0.7.0, 2026-08-13) — a star on each entity's page,
  a signed cookie, filtered and paginated on the server; the admin's curated table is the
  default for everybody who chooses nothing. Two designs were discarded first, and the
  audit of the branch left the site faster than before the feature: `/competitions/`
  2.56s → 0.29s, a competition page 1.64s → 0.03s.
- **The agenda opens at the present and marks what is on** (0.6.0, 2026-08-12) — nothing
  hidden, the badge computed in the browser. Still true and load-bearing: every event has
  `duration = NULL`, so only "started recently" can ever be asserted about event state.
- **The five LOW findings of the review** (0.5.3, 2026-08-12) — including the health probe
  that was 97% of the access log.
- **DNS rebinding in the image downloader** (0.5.2, 2026-08-12) — connections pinned to
  the vetted address, per redirect hop.
- **The upsert window merged real fixtures** (0.5.1, 2026-08-12) — identity exact, date
  changes reconciled per unit with a two-miss grace; its validation task sits in Pending.
- **The deploy relay and the remote targets assumed one container** (0.5.0, 2026-08-12) —
  `scripts/relay.sh` shared with the replica, every remote target iterates.
- **`docker compose pull` failed on the host** (2026-08-12) — `pull_policy: never` on the
  images built there, `make remote-pull` for the rest.
- **The site hid the channel it knew about** (0.4.x, 2026-08-11) — the column names the
  channel for 25 rows of 25 now; its mobile half is still open, in Pending above.
- **The times were right by accident** (2026-08-11) — Spanish wall clock labelled UTC;
  52,133 rows migrated, 287 events verified unmoved across both deploys.
- **The logs were unreadable and the replica had two silent traps** (2026-08-11) —
  `make remote-logs`, `remote-error-check`, and the replica's Traefik rule and UID fixed.
- **500 on non-numeric ids, and a search blind to competitions** (2026-08-11) — `<int:>`
  routes; search covers competition and sport now.
- **Security audit of 2026-08-11, all findings** — closed the same day, Critical to Low:
  Pillow and Django CVE updates, stored XSS through channel link schemes, the image
  downloader hardened (SSRF, size caps, content-derived names), `ALLOWED_HOSTS` tightened
  without breaking the health check, the admin switched off in production behind
  `make remote-admin-on/-off` with a proxy rate limit, `.env.production` out of the image
  and the key rotated, insecure image defaults flipped with a deploy-time gate, dev
  tooling out of the production image, `lxml` pinned, the CSP added without nonces (inline
  moved to static files, Bootstrap off the CDN), and django-bootstrap5 replaced by
  `{% querystring %}` after its pagination dropped the search.
- **Channel matching** (0.2.1, 2026-08-10) — 1,236 queries and 638 ms down to 1 query and
  11 ms, behind 41 characterization tests that first caught two silent bugs.
- **Scraper reporting** (0.3.0, 2026-08-10) — unannounced times counted and named.
- **UI fixes** (0.3.1, 2026-08-11) — crest strip fits one row; expander hides when empty.
- **Production hardening and two self-inflicted outages** (2026-08-10) — `width_field` and
  `SECURE_SSL_REDIRECT`; both carry regression tests and are recorded in `CLAUDE.md`.
- **Performance round** (2026-08-10) — `Event.Meta.ordering` stripped bare; image
  dimensions read from the database, 13.53 ms → 1.68 ms per 40 images.
- **Type hints** (0.2.0, 2026-08-10) — 188 functions annotated, mypy and ruff ANN behind
  them; `channel_matchers.py` deleted.
- **Review blocks A-F** (2026-08-10) — the `env` filter allowlisted, presentation out of
  the models, cache configuration fixed, the triplicated upsert collapsed, MTI settled by
  measurement.
- **Earlier reviews** (Opus 4.6 and Opus 5 rounds) — N+1s, prefetch invalidation, a
  cascade deletion bug, duplicated favourites, and per-request messages leaking into
  cached pages: the incident the caching rules in `CLAUDE.md` descend from.

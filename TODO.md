# Project Improvements TODO

Pending work is listed first, ordered by priority; completed items are kept at the
bottom as a record of what changed and why.

Priority criteria, in order: exposure of the live site at www.mojon.es, then measured
cost on the request path, then maintainability, then cosmetics. Items whose cost is
only paid offline (management commands) or in the admin rank below anything on the
public path.

## Pending

### High

Empty: nothing outstanding currently threatens the live site or the request path.

### Medium

Empty.

### Low

Nothing here is worth doing on its own account; each entry says why it is still open.

1. **`match_channels` runs many queries per imported entry.** Several chained `.exists()`
   probes plus a per-channel `channel.links.filter(...).exists()` inside the import loop.
   **Parked, measured:** 3.1 queries and 2.6 ms per entry, so a 500-entry playlist costs
   **1.3 s** in a command run by hand a few times a month. The remedy is to preload the
   channel names and redo the matching in Python — a rewrite of the logic that decides
   which link attaches to which channel, which is the riskiest code in the importer. Not
   worth it for one second.

2. **Add type hints.** `models.py` has none. **Parked pending a decision on scope:** the
   diff touches every module, so it is worth agreeing first whether it covers only the
   models and querysets or the views and commands too, and whether a checker runs in CI —
   hints nobody verifies drift out of date and mislead.

3. **Revisit MTI performance only if measured.** Not work: a note so it is not reopened
   without profiling. A query count on the real database showed `with_related()` already
   works — reaching `child_event` and then its `competition`, `sport`, `channels` and
   `links` across 25 events costs **0 extra queries**, because the MTI child fetched via
   `select_related` shares the parent's caches.

## Done

### Blocks E and F — 2026-08-10
- [x] **Rewrote `LinkSchemeFilter` to resolve the schemes in the database.** It read every link into Python to parse it, and returned the options from a set, so the dropdown order changed between processes. Now one `DISTINCT` query, ordered, covered by a query-count test.
- [x] **Stopped using private Django API in the admin.** `field._choices` becomes the public `field.choices`, and the generated relation columns are attached once in `__init__`, at registration, instead of being rewritten on the shared `ModelAdmin` instance by every request. The names stay, because five subclasses look them up with `list_display.index(...)`.
- [x] **Gave `self.warnings` an owner.** `import_entries` reads it, so the base command creates it; a subclass that forgot used to break the shared pipeline rather than its own.
- [x] **Replaced the dry-run exception abuse** with `transaction.set_rollback(True)`, removing a `try`/`except` that raised `TransactionManagementError` at itself to force a rollback.
- [x] **Removed the duplicated `is_favorite_event`** — the constant `False` now lives on `Event` and only `Match` overrides it — and **centralised `event_type`**: each subclass declares `EVENT_TYPE` and `Event.save()` applies it, replacing three near-identical `save()` overrides.
- [x] **Made the view context consistent.** `get_base_context(with_teams=False)` replaces the pattern of asking for the favourite teams and popping them back out, the two views that assembled their context by hand now use it, and the function-level imports moved to module scope. Verified the favourites strip still renders on the agenda only, as before.
- [x] **Wrapped the user-facing strings in `gettext_lazy`**, as named constants so they are visible in one place. The site keeps serving them in Spanish — there is no catalogue to translate against — so nothing changed on screen.

### Block D — 2026-08-10
- [x] **Confirmed the `ChannelLink` ordering is intentional.** "Freshest day first, and within that day the order the source listed the links in" is the wanted behaviour, so it stays: collapsing it to `-date_updated` would show every imported batch reversed. Recorded in the comment on `CHANNEL_LINK_ORDERING` so it is not mistaken for an accident again. Worth knowing that `verified` is `False` on all 377 rows, so that tiebreaker never fires until links start being checked.
- [x] **Made the channels page order links the way the rest of the site does.** It sorted only by the keys the template regroups on, so the rows of a single card — which share all three — came back in whatever order the database chose: the same play buttons appeared as `[2413, 2414, 2504, ...]` in the agenda and `[2326, 2324, 2325, ...]` on the channels page, and that order could shift on its own when the table was rebuilt. `CHANNEL_LINK_ORDERING` is now the single definition used by both.
- [x] **Translated the source artifacts to English.** Docstrings, comments and the output of the import commands, along with the Spanish stat keys inside the importer. The web interface stays in Spanish, since that is the language of the site; only code and CLI changed. The few Spanish strings left are comments quoting real channel names from the source data (`"Canal de Tenis" -> "tennis channel"`), which have to stay literal.

### Medium blocks A, B and C — 2026-08-10
- [x] **Restricted the `env` template filter to an allowlist** and **added the missing test modules**. The filter reaches every template, so `{{ "DJANGO_SECRET_KEY"|env }}` would have rendered the secret; only `DJANGO_DEBUG` is readable now. `filters.py` and the template filters had no tests at all and now do.
- [x] **Removed the dead model properties** — `Sport.competitions_with_events`, `competitions_without_events`, `Competition.is_favorite` and `is_favorite_cached` — together with the tests that existed only to keep them alive.
- [x] **Finished decoupling presentation from the models.** The markup moved to `soccertime/rendering.py`, used by the `render_image_markup` filter and by the admin, so there is one implementation instead of a model method plus an unused tag with its own copy of the fallback SVG. Templates lost their `|safe`. Verified the rendered HTML is byte-identical.
- [x] **Fixed the cache configuration**: the file cache path is configurable via `DJANGO_CACHE_LOCATION`, and with caching off the backend is explicitly `DummyCache` rather than a per-process `LocMemCache` that made `cache.clear()` look effective.
- [x] **Collapsed the triplicated upsert in `scrapit`** into one `upsert_event`, cutting the command by a third.

### Production hardening and incidents — 2026-08-10
- [x] **Acted on the media-loss findings.** Deleted `migrate_crests`: a one-off path migration from early 2026 whose "missing or empty file" branch erased crest references instead of leaving them for the scraper to repair, which is how 1357 teams lost theirs. Added `backup-remote-media`, kept on the host rather than inside the volume it protects, since losing that volume is the failure it guards against — 2 MB compressed, so worth keeping even though flags can be re-fetched from their stored URL and crests, which cannot, are exactly what a backup preserves. Both snapshots now rotate to `KEEP_BACKUPS` (2): the database copies had reached 150 MB, six of them taken by a single afternoon of deploys. `redownload_images` reports broken crest references alongside the flags it can restore; the pages themselves keep rendering the fallback icon, so a missing image never breaks the site.
- [x] **Found out why 49 flag files were missing.** They were not deleted one by one: the directory paths never existed in the current media volume, which was created on 2026-02-02 and holds nothing older, while the database rows carrying those paths were already present on 2026-03-07. So the media was lost wholesale around the time that volume was created, and the database kept referring to files that were never copied into it. The scraper hides this, because `get_or_create_flag` re-downloads whenever the file is missing: everything that reappeared healed silently, and after six months the only survivors were the 49 belonging to competitions that never came back — one-off golf and WTA tournaments, Ligue 2 Algeria, Tour de Noruega Femenino. The same event hit crests far harder, and `migrate_crests` made it permanent instead of letting it heal, which is why that command was deleted. Nothing is user-visible today: none of the crestless teams have upcoming matches and no favourite is affected.
- [x] **Verify the deploy automatically instead of by eye.** `deploy-production` reported "completed successfully" both times it left the site broken. It now ends with `remote-smoke-test`: wait for the container to report `healthy`, then fetch every public page **from outside the server**, which is the part that matters — when the health check failed, the application still answered 200 on localhost while the proxy served 404 to the world, so any check run inside the container would have passed. Verified against all three branches: a 404 page fails the run, an unhealthy or missing container fails on timeout, and a healthy deploy passes.
- [x] **Enable the SSL redirect instead of silencing its check.** `security.W008` had been silenced as redundant, since Traefik already answers `http://` with a 301. It turned out to be genuinely fixable: Django only emits the HSTS header when `request.is_secure()` is true, and production does emit it, which proves `SECURE_PROXY_SSL_HEADER` works and the proxy forwards `X-Forwarded-Proto`. `check --deploy` went from 3 silenced checks to 2, and the remaining two — `includeSubDomains` and `preload` — are deliberate policy, not defects.
- [x] **Exempt the health check from that redirect.** Enabling it took the site down: the container health check reaches the app directly over plain HTTP, got a 301, failed, and the orchestrator withdrew the route, so every page returned 404. `SECURE_REDIRECT_EXEMPT` keeps `healthz` unredirected; the regression test reproduces the 301 when the exemption is removed.
- [x] **Restore the 49 flag images missing from the media volume.** Every `Flag` keeps the URL it was fetched from in its `name`, so all of them were recoverable. Added the `redownload_images` command (with `--dry-run`) and `make remote-redownload-images`; production now has 227/227 flags and 3313/3313 crests with both file and dimensions. The download moved to a shared `_image_download` module so `scrapit` and the command share one implementation. The cause was traced afterwards; see the entry below.
- [x] **Codify the production operations that were being done over ad-hoc SSH.** `backup-remote-db` (now run automatically by `deploy-production` before migrating), `list-remote-backups`, `restore-remote-db`, `remote-check` and `remote-clear-cache`. Also fixed `BACKUP_SUFFIX`, which re-ran `date` on every expansion and could name a different file than the one it created.

### Priority round — 2026-08-10
- [x] **Harden the production security settings.** `check --deploy` reported 4 warnings while `/soccertime/admin/login/` answered 200 to the world, so the admin session and CSRF cookies travelled without the `Secure` flag. Added `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_PROXY_SSL_HEADER`, `SECURE_SSL_REDIRECT` and the HSTS trio, all read from the environment through a new `env_flag()` helper so development stays on plain HTTP. Production enables secure cookies, the proxy header and `SECURE_HSTS_SECONDS=31536000`; going straight to a year was backed by checking that the five public pages serve zero `http://` resources, so the usual ramp had nothing left to discover. `includeSubDomains` and `preload` stay off deliberately, and `SECURE_SSL_REDIRECT` stays off because Traefik already answers `http://` with a 301 — the three matching checks are silenced with that rationale, leaving `check --deploy` clean.
- [x] **`Event.Meta.ordering` forced two JOINs and a date cast on every query.** Reduced to `["date"]`, which took `Event` queries from 2 JOINs to 0 and `Match` from 3 to 1, and removed the `django_datetime_cast_date` that defeated the index. The listing order moved into a new `EventQuerySet.chronological()` — `date`, then sport order, then competition name — used by the six views that display events.
- [x] **`render_image` opened every image file to measure it.** `Flag.image` and `Team.crest` now declare `width_field` / `height_field`, migration `0035` backfills the existing rows, and `render_image` reads the dimensions from the database, falling back to the file for rows that predate the change. Measured with fresh instances on a warm cache: **13.53 ms → 1.68 ms** per 40 images, byte-identical markup. The `storage.exists()` probe was kept on purpose — measured at 85 µs against 635 µs for a dimension read, it is cheap insurance against rendering broken images. Writing the tests exposed a real defect in the change: `save_image` handed a bare `BytesIO` to the field, which Django could not measure, and an unnamed `ImageFile` silently stored null dimensions; both are fixed and covered.

### Original backlog
- [x] **Optimize QuerySet/Manager DRYness:** use `EventQuerySet.as_manager()` instead of duplicating every QuerySet method on the Manager.
- [x] **Decouple Presentation from Models:** move the HTML rendering out of `ImageMixin`. Finished later in block B, which put it in `soccertime/rendering.py`.
- [x] **Improve URL Validation:** custom scheme validation for `ChannelLink.link` (`validate_channel_link`).
- [x] **Dynamic Event Durations:** replace the hardcoded 2-hour duration in `Event.date_end` with a `DurationField`.
- [x] **Database Schema Cleanup:** remove the redundant `event_ptr` from the `unique_together` constraints of `Match`, `Race` and `SimpleEvent`.
- [x] **Refine Display Logic:** handle null `team` / `competition` in `Favorite.__str__`.

### Code Review (Opus 4.6)
- [x] **Remove Implicit `.with_related()` in EventManager:** it forced heavy `select_related` / `prefetch_related` JOINs on every query, including `.get()`, `.count()` and internal updates. Now chained explicitly in the views.
- [x] **Fix Global Context N+1:** `get_favorite_competitions()` builds the global context for `base.html`, which reads `competition.flag.flag_image`; the missing `.select_related("flag")` triggered an N+1 on every page load.
- [x] **Fix Admin N+1:** `EventModelAdmin.channels_names` iterated `obj.channels.all()` without prefetching. `get_queryset` now includes `.prefetch_related("channels")`.
- [x] **Avoid Prefetch Invalidation:** `Competition.has_events` / `events_count` used `.filter(...).exists()` / `.count()`, bypassing the prefetch cache. Evaluated in Python instead.
- [x] **Optimize Agenda Aggregation:** `Event.objects.aggregate(Max("date"))` joined every MTI table before computing the maximum.
- [x] **Cache Objects in Scraping Command:** `scrapit.py` called `.get_or_create()` inside loops for Sport, Competition and Team; a local dictionary cache now absorbs those.
- [x] **Avoid `hasattr` as Type Check:** `Event.child_event` relied on `hasattr(self, "match")`, which triggers an implicit query when `select_related` was not used.

### Code Review (Opus 5) — 2026-08-10

Findings marked *(confirmed)* were reproduced with a temporary test before being fixed;
the rest were found by inspection. All were fixed and deployed on 2026-08-10.

- [x] **Deleting a `ChannelLinkSource` wiped unrelated links (data loss)** *(confirmed)*: the receiver deleted **every** `ChannelLink` with zero sources, so a link created manually in the admin was destroyed the first time any source was deleted. Fixed: a `pre_delete` receiver captures the links attached to the source (the through rows are already gone by `post_delete`) and `delete_orphan_channel_links()` only removes those left source-less.
- [x] **Reverse M2M edit crashed** *(confirmed)*: the `m2m_changed` receiver assumed `instance` was always a `ChannelLink`, so `source.links.remove(link)` — what the admin `ChannelLinkSource` form does — raised `AttributeError`. Fixed by honouring `reverse` / `pk_set`, capturing the affected pks in a `pre_clear` branch because `post_clear` does not report them.
- [x] **`/agenda/?events-date=<garbage>` returned HTTP 500** *(confirmed)*: the raw query parameter reached `for_date()` and the ORM raised `ValidationError`. Fixed with `parse_requested_date()`; a malformed value is ignored and the default agenda is served.
- [x] **`favorites()` returned duplicated events** *(confirmed)*: the multi-valued `favorite` reverse FK join duplicated the matches of a team listed in two `Favorite` rows. Fixed with `.distinct()`; `Exists()` subqueries remain a possible follow-up.
- [x] **Scraping aborted when a crest URL was missing** *(confirmed)*: `save_match_event` called `requests.get()` with a possibly `None` URL and caught no network errors, killing the whole run. Fixed with a guarded `download_image()` helper plus `ensure_crest()`.
- [x] **`update_or_create(link=...)` on a non-unique column**: `ChannelLink.link` lost its unique constraint in migration `0029`, so `import_entries` would raise `MultipleObjectsReturned` once two rows shared a link. Migration `0033` merges duplicates into the oldest row — inheriting its sources, channels and `verified` flag — turns empty strings into `NULL`, and restores `unique=True`.
- [x] **Per-request messages leaked into cached pages**: `add_empty_message` added a `django.contrib.messages` entry inside `@cache_page` views, so the banner was stored in the shared page cache and served to unrelated visitors. Fixed: `empty_state()` puts the notice in the context and the templates render `soccertime/empty_state.html`, which also drops one `.exists()` query per view.

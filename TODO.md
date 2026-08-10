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

1. **Restrict the `env` template filter to an allowlist.** `{{ "DJANGO_SECRET_KEY"|env }}`
   renders the secret today; only `DJANGO_DEBUG` is actually used. A footgun rather than
   an open hole — it needs someone to write that in a template — which is why it did not
   rank alongside the transport security work.

2. **Decide the intended `ChannelLink` ordering, then simplify it.** The current
   `["-date_updated__date", "date_updated__time", "-verified", "-id"]` means "newest day
   first, oldest first within that day" and casts the timestamp instead of using an
   index, exactly like the `Event` ordering that was just fixed. Collapsing it to
   `["-date_updated", "-verified", "-id"]` is a behaviour change, not just an
   optimization — confirm the sort is intentional first.

3. **Add the missing test modules.** Nothing covers `soccertime/filters.py`
   (`LinkSchemeFilter`) or `soccertime/templatetags/soccertime_tags.py` (`env`,
   `sort_by_list_length`, `normalize_subcategory`, `sort_categories_by_total_links`,
   `render_image_markup`). Writing tests is a project rule, and item 1 needs them anyway.

4. **Remove the unused model properties.** `Sport.competitions_with_events` /
   `competitions_without_events` were superseded by the aggregation in the `competitions`
   view, and `Competition.is_favorite` / `is_favorite_cached` are byte-identical
   duplicates that no template or view uses — `competitions.html` reads the `is_fav`
   annotation. Delete them together with the tests that only exist to keep them alive.

5. **Finish decoupling presentation from the models.** The migration stopped half way:
   `render_image_markup` in `soccertime_tags.py` is used by no template and carries a
   second copy of `FALLBACK_SVG` duplicating `ImageMixin.FALLBACK_SVG`, while
   `base.html`, `agenda_item.html` and `competitions.html` still call
   `flag_image|safe` / `crest_image|safe` on the model. Pick one mechanism: either move
   the templates onto the tag and drop `render_image` from the model, or delete the tag.
   Whichever wins must keep reading the stored dimensions rather than the file.

6. **Translate the source artifacts to English.** Docstrings and comments across
   `models.py`, `views.py`, `_link_import_base.py`, `soccertime_tags.py` and the import
   commands are in Spanish, and the import commands print Spanish output
   (`"Canal no encontrado"`, `"RESUMEN"`). The project convention is English for all
   code, comments and documentation; every future edit pays this tax.

7. **Fix the cache configuration.** The file-based cache path
   `/var/tmp/soccertime_cache` is hardcoded, and when caching is disabled Django falls
   back to `LocMemCache`, so the `cache.clear()` calls in the management commands only
   affect the calling process. Make the location configurable and select `DummyCache`
   explicitly when caching is off.

8. **Collapse the triplicated upsert in `scrapit`.** `save_simple_event`,
   `save_race_event` and `save_match_event` are the same get / update / dedupe algorithm
   copy-pasted per model. Extract one `_upsert_event(model, lookup, event_datetime)`.

### Low

9. **Stop using private Django API in the admin.** `AutoModelAdmin.get_list_filter`
   filters on `field._choices`; the public `field.choices` is equivalent and will not
   break on an upgrade. `get_list_display` also mutates the shared `ModelAdmin`
   singleton with `setattr(self, ...)` per request — harmless today because the
   generated callables are equivalent, but it should build a local mapping instead.

10. **Wrap the user-facing strings in `gettext_lazy`.** The `empty_state()` defaults in
    `views.py` (`"No hay eventos a la vista :)"`, `"No hay canales disponibles :_("`) are
    hardcoded while the templates already use `{% translate %}`.

11. **Make the view context consistent.** `team_events` and `competition_events` rebuild
    the context by hand instead of using `get_base_context()`, and both `team_events` and
    `competitions` use function-level imports (`from soccertime.models import Match`,
    `from django.db.models import Exists, OuterRef`). Move the imports to module scope and
    reuse the shared helper.

12. **Give `self.warnings` an owner.** `BaseLinkImportCommand.import_entries` reads it,
    but only each subclass's `handle()` initialises it, so a new subclass breaks the
    pipeline. Initialise it in the base class.

13. **Replace the dry-run exception abuse.** `import_entries` triggers its rollback by
    raising `transaction.TransactionManagementError` and catching it. Use
    `transaction.set_rollback(True)` or a dedicated private exception.

14. **Deduplicate `is_favorite_event`.** `Race` and `SimpleEvent` both define it
    returning `False`. Move the default to `Event` and override only in `Match`.

15. **`LinkSchemeFilter` reads every link URL.** It iterates the whole `ChannelLink`
    table on each admin list render to build the scheme dropdown. Negligible at today's
    377 rows and admin-only, hence the low rank; persist the scheme or cache a
    `values_list(...).distinct()` if the table grows.

16. **`match_channels` runs many queries per imported entry.** Several chained
    `.exists()` probes plus a per-channel `channel.links.filter(...).exists()` inside the
    import loop. Offline cost only. Preload the channel names and match in Python if
    large playlists become slow.

17. **Centralize the `event_type` logic.** Set it in the base `Event.save()` or a
    `pre_save` signal instead of repeating the assignment in every subclass.

18. **Add type hints** to models, managers and querysets for IDE support and earlier
    error detection.

19. **Revisit MTI performance only if measured.** Originally filed as high priority, but
    a query-count check on the real database showed `with_related()` already works:
    reaching `child_event` and then its `competition`, `sport`, `channels` and `links`
    across 25 events costs **0 extra queries**, because the MTI child fetched via
    `select_related` shares the parent's caches. Reach for `django-model-utils`'
    `InheritanceManager` only if profiling later shows JOIN overhead.

## Done

### Production hardening and incidents — 2026-08-10
- [x] **Acted on the media-loss findings.** Deleted `migrate_crests`: a one-off path migration from early 2026 whose "missing or empty file" branch erased crest references instead of leaving them for the scraper to repair, which is how 1357 teams lost theirs. Added `backup-remote-media`, kept on the host rather than inside the volume it protects, since losing that volume is the failure it guards against — 2 MB compressed, so worth keeping even though flags can be re-fetched from their stored URL and crests, which cannot, are exactly what a backup preserves. Both snapshots now rotate to `KEEP_BACKUPS` (2): the database copies had reached 150 MB, six of them taken by a single afternoon of deploys. `redownload_images` reports broken crest references alongside the flags it can restore; the pages themselves keep rendering the fallback icon, so a missing image never breaks the site.
- [x] **Found out why 49 flag files were missing.** They were not deleted one by one: the directory paths never existed in the current media volume, which was created on 2026-02-02 and holds nothing older, while the database rows carrying those paths were already present on 2026-03-07. So the media was lost wholesale around the time that volume was created, and the database kept referring to files that were never copied into it. The scraper hides this, because `get_or_create_flag` re-downloads whenever the file is missing: everything that reappeared healed silently, and after six months the only survivors were the 49 belonging to competitions that never came back — one-off golf and WTA tournaments, Ligue 2 Algeria, Tour de Noruega Femenino. The same event hit crests far harder, and `migrate_crests` made it permanent instead of letting it heal; see pending items 1 to 3. Nothing is user-visible today: none of the crestless teams have upcoming matches and no favourite is affected.
- [x] **Verify the deploy automatically instead of by eye.** `deploy-production` reported "completed successfully" both times it left the site broken. It now ends with `remote-smoke-test`: wait for the container to report `healthy`, then fetch every public page **from outside the server**, which is the part that matters — when the health check failed, the application still answered 200 on localhost while the proxy served 404 to the world, so any check run inside the container would have passed. Verified against all three branches: a 404 page fails the run, an unhealthy or missing container fails on timeout, and a healthy deploy passes.
- [x] **Enable the SSL redirect instead of silencing its check.** `security.W008` had been silenced as redundant, since Traefik already answers `http://` with a 301. It turned out to be genuinely fixable: Django only emits the HSTS header when `request.is_secure()` is true, and production does emit it, which proves `SECURE_PROXY_SSL_HEADER` works and the proxy forwards `X-Forwarded-Proto`. `check --deploy` went from 3 silenced checks to 2, and the remaining two — `includeSubDomains` and `preload` — are deliberate policy, not defects.
- [x] **Exempt the health check from that redirect.** Enabling it took the site down: the container health check reaches the app directly over plain HTTP, got a 301, failed, and the orchestrator withdrew the route, so every page returned 404. `SECURE_REDIRECT_EXEMPT` keeps `healthz` unredirected; the regression test reproduces the 301 when the exemption is removed.
- [x] **Restore the 49 flag images missing from the media volume.** Every `Flag` keeps the URL it was fetched from in its `name`, so all of them were recoverable. Added the `redownload_images` command (with `--dry-run`) and `make remote-redownload-images`; production now has 227/227 flags and 3313/3313 crests with both file and dimensions. The download moved to a shared `_image_download` module so `scrapit` and the command share one implementation. The cause of the loss is still unknown — see pending item 2.
- [x] **Codify the production operations that were being done over ad-hoc SSH.** `backup-remote-db` (now run automatically by `deploy-production` before migrating), `list-remote-backups`, `restore-remote-db`, `remote-check` and `remote-clear-cache`. Also fixed `BACKUP_SUFFIX`, which re-ran `date` on every expansion and could name a different file than the one it created.

### Priority round — 2026-08-10
- [x] **Harden the production security settings.** `check --deploy` reported 4 warnings while `/soccertime/admin/login/` answered 200 to the world, so the admin session and CSRF cookies travelled without the `Secure` flag. Added `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_PROXY_SSL_HEADER`, `SECURE_SSL_REDIRECT` and the HSTS trio, all read from the environment through a new `env_flag()` helper so development stays on plain HTTP. Production enables secure cookies, the proxy header and `SECURE_HSTS_SECONDS=31536000`; going straight to a year was backed by checking that the five public pages serve zero `http://` resources, so the usual ramp had nothing left to discover. `includeSubDomains` and `preload` stay off deliberately, and `SECURE_SSL_REDIRECT` stays off because Traefik already answers `http://` with a 301 — the three matching checks are silenced with that rationale, leaving `check --deploy` clean.
- [x] **`Event.Meta.ordering` forced two JOINs and a date cast on every query.** Reduced to `["date"]`, which took `Event` queries from 2 JOINs to 0 and `Match` from 3 to 1, and removed the `django_datetime_cast_date` that defeated the index. The listing order moved into a new `EventQuerySet.chronological()` — `date`, then sport order, then competition name — used by the six views that display events.
- [x] **`render_image` opened every image file to measure it.** `Flag.image` and `Team.crest` now declare `width_field` / `height_field`, migration `0035` backfills the existing rows, and `render_image` reads the dimensions from the database, falling back to the file for rows that predate the change. Measured with fresh instances on a warm cache: **13.53 ms → 1.68 ms** per 40 images, byte-identical markup. The `storage.exists()` probe was kept on purpose — measured at 85 µs against 635 µs for a dimension read, it is cheap insurance against rendering broken images. Writing the tests exposed a real defect in the change: `save_image` handed a bare `BytesIO` to the field, which Django could not measure, and an unnamed `ImageFile` silently stored null dimensions; both are fixed and covered.

### Original backlog
- [x] **Optimize QuerySet/Manager DRYness:** use `EventQuerySet.as_manager()` instead of duplicating every QuerySet method on the Manager.
- [x] **Decouple Presentation from Models:** move the HTML rendering out of `ImageMixin` (partially — see pending item 8).
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

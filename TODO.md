# Project Improvements TODO

This list outlines recommended architectural and performance improvements for the Soccertime project, categorized by priority.

## High Priority
- [x] **Optimize QuerySet/Manager DRYness:** Use `EventQuerySet.as_manager()` in the `Event` model instead of manually duplicating every method from the QuerySet to the Manager.
- [ ] **Performance Review of MTI:** Monitor performance of Multi-table Inheritance (MTI) for Events. Consider using `django-model-utils`'s `InheritanceManager` to fetch subclasses efficiently if JOIN overhead becomes a bottleneck.

## Medium Priority
- [x] **Decouple Presentation from Models:** Remove HTML rendering logic (`render_image`) from `ImageMixin`. Move this to a template tag or return attributes for the template to handle.
- [x] **Improve URL Validation:** Change `ChannelLink.link` to include custom URL scheme validation (`validate_channel_link`).
- [x] **Dynamic Event Durations:** Replace the hardcoded 2-hour duration in `Event.date_end` with a `DurationField` to allow sport-specific timings.
- [ ] **Optimize Ordering Index:** Simplify `ChannelLink` ordering to use the full `date_updated` timestamp (`ordering = ["-date_updated", "-verified", "-id"]`) for better database performance.

## Low Priority
- [ ] **Centralize `event_type` logic:** Automate the setting of `event_type` in the base `Event.save()` method or a `pre_save` signal to avoid repetition in subclasses.
- [x] **Database Schema Cleanup:** Remove redundant `event_ptr` from `unique_together` constraints in `Match`, `Race`, and `SimpleEvent`.
- [x] **Refine Display Logic:** Update `Favorite.__str__` to handle edge cases where either `team` or `competition` might be null more gracefully.
- [ ] **Developer Experience:** Add Python type hints to models, managers, and querysets to improve IDE support and catch potential bugs early.

## Code Review (Opus 4.6)

### Architecture & Performance
- [x] **Remove Implicit `.with_related()` in EventManager:** The default manager `Event.objects` calls `.with_related()` implicitly inside `get_queryset()`. This forces heavy `select_related` and `prefetch_related` JOINs on every query, including `.get()`, `.count()`, and internal updates. Remove it from the default manager and chain it explicitly in views (e.g., `Event.objects.with_related().for_date(...)`), or use a secondary manager for views.
- [x] **Fix Global Context N+1:** `get_favorite_competitions()` in `views.py` is used to build the global context for `base.html`. The template iterates over these competitions and accesses `competition.flag.flag_image`. Since `.select_related("flag")` is missing in the queryset, it triggers an N+1 query on **every page load**.
- [x] **Fix Admin N+1:** The `EventModelAdmin` adds a `channels_names` column that iterates over `obj.channels.all()`. Since `channels` are not prefetched in the admin queryset, this generates an N+1 query in the event list view. Override `get_queryset` to include `.prefetch_related("channels")`.
- [x] **Avoid Prefetch Invalidation:** Properties like `Competition.has_events` and `Competition.events_count` use `.filter(...).exists()` and `.filter(...).count()`. This bypasses the prefetch cache and hits the database every time. Use Python-side evaluation (e.g., list comprehensions or `len()`) when the queryset is prefetched.
- [x] **Optimize Agenda Aggregation:** In `agenda` view, `Event.objects.aggregate(Max("date"))` is used. Due to the default `EventManager`, this performs unnecessary JOINs across all MTI tables before computing the maximum.

### SOLID & DRY Best Practices
- [x] **Cache Objects in Scraping Command:** The `scrapit.py` command heavily hits the database with `.get_or_create()` inside loops for frequently used objects (Sport, Competition, Team). Implement a local Python dictionary cache within the command to reduce database load.
- [x] **Avoid `hasattr` as Type Check:** `Event.child_event` relies on `hasattr(self, "match")`. If `.select_related` was not used, this catches the `ObjectDoesNotExist` exception but only after triggering an implicit database query. Document this coupling clearly or rely on the `event_type` attribute to avoid accidental DB hits.

## Code Review (Opus 5) — 2026-08-10

Findings marked *(confirmed)* were reproduced with a temporary test against the
project test suite; the rest were found by inspection.

### Bugs
- [x] **Deleting a `ChannelLinkSource` wipes unrelated links (data loss)** *(confirmed)*: `delete_orphan_channel_links_on_source_delete` deleted **every** `ChannelLink` with zero sources, not just the ones that belonged to the deleted source, so a link created manually in the admin was destroyed the first time any source was deleted. Fixed: a `pre_delete` receiver captures the links attached to the source (the through rows are already gone by `post_delete`) and the shared `delete_orphan_channel_links()` helper only removes those that ended up source-less.
- [x] **Reverse M2M edit crashes** *(confirmed)*: `delete_orphan_channel_links_on_m2m` assumed `instance` was always a `ChannelLink`, so `source.links.remove(link)` (what the admin `ChannelLinkSource` form does) raised `AttributeError: 'ChannelLinkSource' object has no attribute 'sources'`. Fixed: the receiver now honours `reverse` / `pk_set`, and captures the affected pks in a `pre_clear` branch because `post_clear` does not report them.
- [x] **`/agenda/?events-date=<garbage>` returns HTTP 500** *(confirmed)*: the raw query parameter went straight into `for_date()` and the ORM raised `ValidationError`. Fixed with a `parse_requested_date()` helper in `views.py`; a malformed value is ignored and the default `today_onwards()` agenda is served.
- [x] **`favorites()` returns duplicated events** *(confirmed)*: the multi-valued `favorite` reverse FK join made the matches of a team listed in two `Favorite` rows appear twice on the landing page. Fixed with `.distinct()` in `EventQuerySet.favorites`. Converting the joins to `Exists()` subqueries remains a possible follow-up (see Performance).
- [x] **Scraping aborts when a crest URL is missing** *(confirmed)*: `save_match_event` called `requests.get()` with a possibly `None` URL (`MissingSchema`) and did not catch network errors, killing the whole run. Fixed with a single guarded `download_image()` helper (used by the flag and both crests) plus `ensure_crest()`; failures are reported on stderr and skipped.
- [ ] **`update_or_create(link=...)` on a non-unique column**: `ChannelLink.link` has no unique constraint (dropped in migration `0029`), so `import_entries` (`soccertime/management/commands/_link_import_base.py:260`) raises `MultipleObjectsReturned` as soon as two rows share a link. Add a `UniqueConstraint` on `link` (plus a data migration to dedupe) or handle the exception.
- [ ] **Per-request messages leak into cached pages**: `add_empty_message` adds a `django.contrib.messages` entry inside views decorated with `@cache_page`. The rendered banner is stored in the shared page cache and served to unrelated visitors, while the originating user's cookie message is never consumed. Render the empty state from the template context instead of the messages framework.

### Performance
- [ ] **`Event.Meta.ordering` forces two JOINs and a date cast on every query** *(confirmed via generated SQL)*: `ordering = ["date__date", "date", "competition__sport", "competition"]` produces `INNER JOIN competition INNER JOIN sport ORDER BY django_datetime_cast_date(date, UTC, UTC), date, sport.order, competition.name` for *every* `Event` query, including `.count()`, `.exists()`, admin lists and internal updates. `date__date, date` is also redundant — ordering by the timestamp already orders by day. Reduce the default to `["date"]` and apply the sport/competition ordering explicitly in the views that need it.
- [ ] **`ChannelLink` ordering note**: the pending "Optimize Ordering Index" item above is a behaviour change, not just an optimization — the current `-date_updated__date, date_updated__time` means "newest day first, oldest first within that day". Confirm the intended sort before collapsing it to `-date_updated`.
- [ ] **`render_image` hits the filesystem on every render**: `ImageMixin.render_image` (`soccertime/models.py:93`) calls `storage.exists()` (a `stat`) and reads `image.width` / `image.height` (which opens and parses the image header) for each crest and flag. An agenda page with 25 events issues hundreds of filesystem operations per request. Add `width_field` / `height_field` to the `ImageField`s (cached in the DB) and drop the `exists()` probe or cache it.
- [ ] **`LinkSchemeFilter` loads every link URL into memory**: `soccertime/filters.py:12` iterates the full `ChannelLink` table on each admin list render just to build the scheme dropdown. Persist the scheme (or derive the lookups from a cached `values_list(...).distinct()` query).
- [ ] **`match_channels` runs many queries per imported entry**: `_link_import_base.py:127` chains several `.exists()` probes plus a per-channel `channel.links.filter(...).exists()` inside the import loop. Preload the channel names once into memory and match in Python for large playlists.

### SOLID & DRY
- [ ] **Dead code — unused model properties**: `Sport.competitions_with_events` / `competitions_without_events` (`models.py:45-60`) were superseded by the aggregation in the `competitions` view, and `Competition.is_favorite` / `is_favorite_cached` are byte-identical duplicates that no template or view uses (`competitions.html` uses the `is_fav` annotation). Delete them together with the tests that only exist to keep them alive.
- [ ] **Dead code — `render_image_markup` template tag**: `soccertime/templatetags/soccertime_tags.py:66` is never used by any template, and it carries a second copy of `FALLBACK_SVG` that duplicates `ImageMixin.FALLBACK_SVG`. Either finish the "Decouple Presentation from Models" migration (switch `base.html`, `agenda_item.html` and `competitions.html` from `flag_image|safe` / `crest_image|safe` to the tag, and drop `render_image` from the model) or remove the tag. Right now both mechanisms exist and neither is authoritative.
- [ ] **`scrapit` duplicates its upsert logic three times**: `save_simple_event`, `save_race_event` and `save_match_event` are the same get / update / dedupe algorithm copy-pasted per model. Extract one `_upsert_event(model, lookup, event_datetime)` helper.
- [ ] **`is_favorite_event` duplicated**: `Race` and `SimpleEvent` both define `is_favorite_event` returning `False`. Move the default to `Event` and override only in `Match`.
- [ ] **Inconsistent view context**: `team_events` and `competition_events` rebuild the context by hand instead of using `get_base_context()`, and both use function-level imports (`from soccertime.models import Match`, `from django.db.models import Exists, OuterRef` in `competitions`). Move the imports to module scope and reuse the shared context helper.
- [ ] **`self.warnings` is defined outside its owner**: `BaseLinkImportCommand.import_entries` reads `self.warnings`, but the attribute is only initialised in each subclass's `handle()`. Initialise it in the base class so the pipeline cannot break on a new subclass.
- [ ] **Dry-run implemented via exception abuse**: `import_entries` triggers a rollback by raising `transaction.TransactionManagementError` and catching it. Use `transaction.set_rollback(True)` or a dedicated private exception.
- [ ] **Private Django API in the admin**: `AutoModelAdmin.get_list_filter` (`admin.py:72`) filters on `field._choices`; use the public `field.choices`. `get_list_display` also mutates the shared `ModelAdmin` singleton with `setattr(self, ...)` per request — build the callables in a local mapping instead.

### Conventions, Testing & Config
- [ ] **Spanish in source artifacts**: docstrings and comments across `models.py`, `views.py`, `_link_import_base.py`, `soccertime_tags.py` and the import commands are in Spanish, and the import commands print Spanish output (`"Canal no encontrado"`, `"RESUMEN"`). Project convention is English for all code, comments and documentation.
- [ ] **Untranslated user-facing strings in views**: `add_empty_message` defaults (`"No hay eventos a la vista :)"`, `"No hay canales disponibles :_("`) are hardcoded in `views.py` while the templates already use `{% translate %}`. Wrap them in `gettext_lazy`.
- [ ] **Missing tests**: there is no test module for `soccertime/filters.py` (`LinkSchemeFilter`) or `soccertime/templatetags/soccertime_tags.py` (`env`, `sort_by_list_length`, `normalize_subcategory`, `sort_categories_by_total_links`, `render_image_markup`). Add unit tests, plus regression tests for each bug listed above.
- [ ] **`env` template filter exposes the whole environment**: `{{ "DJANGO_SECRET_KEY"|env }}` renders the secret. Restrict the filter to an explicit allowlist of keys (currently only `DJANGO_DEBUG` is used).
- [ ] **Production security settings absent**: no `SECURE_SSL_REDIRECT`, `SECURE_HSTS_SECONDS`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE` or `SECURE_PROXY_SSL_HEADER` in `settings.py`. Run `manage.py check --deploy` and configure the flags from the environment.
- [ ] **Cache configuration**: the file-based cache path `/var/tmp/soccertime_cache` is hardcoded, and when caching is disabled Django silently falls back to `LocMemCache`, so the `cache.clear()` calls in the management commands affect only the calling process. Make the location configurable and select `DummyCache` explicitly when caching is off.

# Project Improvements TODO

This list outlines recommended architectural and performance improvements for the Soccertime project, categorized by priority.

## High Priority
- [ ] **Optimize QuerySet/Manager DRYness:** Use `EventQuerySet.as_manager()` in the `Event` model instead of manually duplicating every method from the QuerySet to the Manager.
- [ ] **Performance Review of MTI:** Monitor performance of Multi-table Inheritance (MTI) for Events. Consider using `django-model-utils`'s `InheritanceManager` to fetch subclasses efficiently if JOIN overhead becomes a bottleneck.

## Medium Priority
- [ ] **Decouple Presentation from Models:** Remove HTML rendering logic (`render_image`) from `ImageMixin`. Move this to a template tag or return attributes for the template to handle.
- [ ] **Improve URL Validation:** Change `ChannelLink.link` from `CharField` to `URLField(max_length=1000)` to benefit from built-in validation.
- [ ] **Dynamic Event Durations:** Replace the hardcoded 2-hour duration in `Event.date_end` with a `DurationField` to allow sport-specific timings.
- [ ] **Optimize Ordering Index:** Simplify `ChannelLink` ordering to use the full `date_updated` timestamp (`ordering = ["-date_updated", "-verified", "-id"]`) for better database performance.

## Low Priority
- [ ] **Centralize `event_type` logic:** Automate the setting of `event_type` in the base `Event.save()` method or a `pre_save` signal to avoid repetition in subclasses.
- [ ] **Database Schema Cleanup:** Remove redundant `event_ptr` from `unique_together` constraints in `Match`, `Race`, and `SimpleEvent`.
- [ ] **Refine Display Logic:** Update `Favorite.__str__` to handle edge cases where either `team` or `competition` might be null more gracefully.
- [ ] **Developer Experience:** Add Python type hints to models, managers, and querysets to improve IDE support and catch potential bugs early.

## Code Review (Opus 4.6)

### Architecture & Performance
- [ ] **Remove Implicit `.with_related()` in EventManager:** The default manager `Event.objects` calls `.with_related()` implicitly inside `get_queryset()`. This forces heavy `select_related` and `prefetch_related` JOINs on every query, including `.get()`, `.count()`, and internal updates. Remove it from the default manager and chain it explicitly in views (e.g., `Event.objects.with_related().for_date(...)`), or use a secondary manager for views.
- [ ] **Fix Global Context N+1:** `get_favorite_competitions()` in `views.py` is used to build the global context for `base.html`. The template iterates over these competitions and accesses `competition.flag.flag_image`. Since `.select_related("flag")` is missing in the queryset, it triggers an N+1 query on **every page load**.
- [ ] **Fix Admin N+1:** The `EventModelAdmin` adds a `channels_names` column that iterates over `obj.channels.all()`. Since `channels` are not prefetched in the admin queryset, this generates an N+1 query in the event list view. Override `get_queryset` to include `.prefetch_related("channels")`.
- [ ] **Avoid Prefetch Invalidation:** Properties like `Competition.has_events` and `Competition.events_count` use `.filter(...).exists()` and `.filter(...).count()`. This bypasses the prefetch cache and hits the database every time. Use Python-side evaluation (e.g., list comprehensions or `len()`) when the queryset is prefetched.
- [ ] **Optimize Agenda Aggregation:** In `agenda` view, `Event.objects.aggregate(Max("date"))` is used. Due to the default `EventManager`, this performs unnecessary JOINs across all MTI tables before computing the maximum.

### SOLID & DRY Best Practices
- [ ] **Cache Objects in Scraping Command:** The `scrapit.py` command heavily hits the database with `.get_or_create()` inside loops for frequently used objects (Sport, Competition, Team). Implement a local Python dictionary cache within the command to reduce database load.
- [ ] **Avoid `hasattr` as Type Check:** `Event.child_event` relies on `hasattr(self, "match")`. If `.select_related` was not used, this catches the `ObjectDoesNotExist` exception but only after triggering an implicit database query. Document this coupling clearly or rely on the `event_type` attribute to avoid accidental DB hits.

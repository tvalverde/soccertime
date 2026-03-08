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

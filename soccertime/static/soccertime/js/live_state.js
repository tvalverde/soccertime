/* Marks the events that are on right now.

   Decided in the browser, not on the server, because every listing is cached for an hour:
   a badge rendered with the page would go on claiming an event is live up to sixty minutes
   after it ended, and would be missing from one that started meanwhile.

   The window is deliberately short. Every event stores `duration = NULL`, so the only end
   available is a flat two-hour default, and 30% of future events are in sports where that
   is wrong — a cycling stage runs five hours, golf all day. So this errs towards silence:
   it never says something is live once that window has passed, which means a long event
   loses its badge while still running. Claiming wrongly is the worse mistake on a page
   whose whole job is telling you what to watch.

   Without this script every row renders exactly as it would otherwise: the badge is an
   addition, never the only carrier of something. */

document.addEventListener('DOMContentLoaded', function () {
  const LIVE_WINDOW_MS = 2 * 60 * 60 * 1000;
  const now = Date.now();

  document.querySelectorAll('tr[data-starts-at]').forEach(function (row) {
    const startedAt = Date.parse(row.dataset.startsAt);
    if (Number.isNaN(startedAt)) {
      return;
    }
    const elapsed = now - startedAt;
    if (elapsed < 0 || elapsed > LIVE_WINDOW_MS) {
      return;
    }
    row.classList.add('event-live');
    const badge = row.querySelector('.live-badge');
    if (badge) {
      badge.classList.remove('d-none');
    }
  });
});

/* Shows or hides the favourite-team crest strip, and hides its own button when there is
   nothing to reveal.

   This lived in a <script> block inside base.html. It is a file now because the
   Content-Security-Policy allows scripts only from this origin, with no 'unsafe-inline'
   and no nonce — a nonce cannot work here, since every public page is cached for an hour
   and the nonce in a cached body would not match the one in the freshly built header. */

document.addEventListener('DOMContentLoaded', function () {
  const btn = document.getElementById('toggle-teams-btn');
  const container = document.getElementById('teams-container');
  const icon = document.getElementById('toggle-teams-icon');

  if (btn && container) {
    // Also set as `max-height` on `.teams-strip` in theme.css. Change both together.
    const COLLAPSED_HEIGHT = 44;

    // Whether the strip overflows depends on the rendered layout: the viewport
    // width, how many crests there are and how big they are. The server cannot
    // know that, so the button ships with the page and hides itself here when
    // there is nothing underneath to reveal.
    function syncButtonVisibility() {
      if (btn.getAttribute('aria-expanded') === 'true') return;
      const overflows = container.scrollHeight > COLLAPSED_HEIGHT + 1;
      btn.classList.toggle('d-none', !overflows);
    }

    syncButtonVisibility();
    window.addEventListener('resize', syncButtonVisibility);
    // Crests arriving late change the height, so re-check once everything loads.
    window.addEventListener('load', syncButtonVisibility);

    btn.addEventListener('click', function () {
      // Empty on the first click: the collapsed height now comes from `.teams-strip`
      // rather than from a style attribute, so nothing has been written here yet.
      // Assigning through the CSSOM stays allowed under the policy; only style
      // attributes and <style> blocks in the markup are refused.
      const collapsed = container.style.maxHeight === COLLAPSED_HEIGHT + 'px' || container.style.maxHeight === '';
      if (collapsed) {
        container.style.maxHeight = '1000px';
        icon.innerHTML = '<path fill-rule="evenodd" d="M7.646 4.646a.5.5 0 0 1 .708 0l6 6a.5.5 0 0 1-.708.708L8 5.707l-5.646 5.647a.5.5 0 0 1-.708-.708l6-6z"/>';
        btn.setAttribute('aria-expanded', 'true');
      } else {
        container.style.maxHeight = COLLAPSED_HEIGHT + 'px';
        icon.innerHTML = '<path fill-rule="evenodd" d="M1.646 4.646a.5.5 0 0 1 .708 0L8 10.293l5.646-5.647a.5.5 0 0 1 .708.708l-6 6a.5.5 0 0 1-.708 0l-6-6a.5.5 0 0 1 0-.708z"/>';
        btn.setAttribute('aria-expanded', 'false');
      }
    });
  }
});

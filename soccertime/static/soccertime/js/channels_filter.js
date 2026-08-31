/* The channels page filter and its hash deep links.
 *
 * A file rather than an inline script because the Content-Security-Policy allows neither
 * 'unsafe-inline' nor a nonce (cached bodies outlive nonces). Client-side because the
 * page is one cached body holding every source: filtering here costs no request and
 * cannot fragment the cache the way the old `?subcategory=` tabs did.
 *
 * Without this script the page still works: Bootstrap's data API switches tabs and
 * expands categories, and the filter input stays hidden, so no visitor sees a dead
 * control. Cards carry their searchable text in `data-search`, already folded by
 * `soccertime.text.fold`; `fold()` below has to keep matching it.
 */
document.addEventListener('DOMContentLoaded', function () {
  const input = document.getElementById('channels-filter');
  if (!input) {
    return;
  }

  document.getElementById('channels-filter-wrap').classList.remove('d-none');

  const hint = document.getElementById('channels-filter-hint');
  const panes = Array.from(document.querySelectorAll('[data-source-pane]'));
  const tabButtons = Array.from(document.querySelectorAll('[data-source-slug]'));

  /* Mirror of soccertime.text.fold: lower case, diacritics dropped. */
  function fold(text) {
    return text.toLowerCase().normalize('NFD').replace(/\p{M}/gu, '');
  }

  function badgeFor(pane) {
    const button = document.querySelector('[data-bs-target="#' + pane.id + '"]');
    return button ? button.querySelector('[data-count-badge]') : null;
  }

  function setExpanded(collapse, expanded) {
    collapse.classList.toggle('show', expanded);
    const item = collapse.closest('[data-category-item]');
    const button = item.querySelector('.accordion-button');
    button.classList.toggle('collapsed', !expanded);
    button.setAttribute('aria-expanded', expanded ? 'true' : 'false');
  }

  function filterPane(pane, tokens) {
    const filtering = tokens.length > 0;
    let matches = 0;

    pane.querySelectorAll('[data-search]').forEach(function (card) {
      const match = tokens.every(function (token) {
        return card.dataset.search.includes(token);
      });
      card.classList.toggle('d-none', filtering && !match);
      if (match) {
        matches += 1;
      }
    });

    pane.querySelectorAll('[data-category-item]').forEach(function (item) {
      const hasVisible = item.querySelector('[data-search]:not(.d-none)') !== null;
      item.classList.toggle('d-none', filtering && !hasVisible);

      const collapse = item.querySelector('[data-category-collapse]');
      if (filtering) {
        // Remember how the visitor left the category once, so clearing the filter
        // restores their accordion instead of leaving everything open.
        if (!('wasOpen' in collapse.dataset)) {
          collapse.dataset.wasOpen = collapse.classList.contains('show') ? 'true' : 'false';
        }
        if (hasVisible) {
          setExpanded(collapse, true);
        }
      } else if ('wasOpen' in collapse.dataset) {
        setExpanded(collapse, collapse.dataset.wasOpen === 'true');
        delete collapse.dataset.wasOpen;
      }
    });

    const unmatchedSection = pane.querySelector('[data-unmatched-section]');
    if (unmatchedSection) {
      const hasVisible = unmatchedSection.querySelector('[data-search]:not(.d-none)') !== null;
      unmatchedSection.classList.toggle('d-none', filtering && !hasVisible);
    }

    const badge = badgeFor(pane);
    if (badge) {
      badge.textContent = filtering ? String(matches) : badge.dataset.total;
      // While filtering the badge answers a different question — matches, not size —
      // and the primary colour is what count badges use for "this is the number".
      badge.classList.toggle('bg-primary', filtering);
      badge.classList.toggle('bg-secondary', !filtering);
    }

    return matches;
  }

  function updateHint(query, matchesByPane) {
    const filtering = query !== '';
    hint.classList.toggle('d-none', !filtering);
    if (!filtering) {
      hint.textContent = '';
      return;
    }

    const total = matchesByPane.reduce(function (sum, entry) {
      return sum + entry.matches;
    }, 0);
    if (total === 0) {
      hint.textContent = hint.dataset.templateNone.replace('%QUERY%', query);
      return;
    }

    const template = total === 1 ? hint.dataset.templateSingular : hint.dataset.templatePlural;
    const summary = template.replace('%COUNT%', String(total)).replace('%QUERY%', query);
    const parts = matchesByPane
      .filter(function (entry) {
        return entry.matches > 0;
      })
      .map(function (entry) {
        return hint.dataset.templateSource
          .replace('%COUNT%', String(entry.matches))
          .replace('%SOURCE%', entry.name);
      });
    hint.textContent = parts.length > 1 ? summary + ' — ' + parts.join(', ') : summary;
  }

  function applyFilter() {
    const query = input.value.trim();
    const tokens = fold(query).split(/\s+/).filter(Boolean);
    const matchesByPane = panes.map(function (pane) {
      return { name: pane.dataset.sourceName, matches: filterPane(pane, tokens) };
    });
    updateHint(query, matchesByPane);
  }

  input.addEventListener('input', applyFilter);

  /* Hash deep links: #elcano opens the Elcano tab. The panes' ids carry a `source-`
   * prefix on purpose, so the bare hash never names an element and the browser does not
   * scroll-jump on load. */
  const slug = window.location.hash.slice(1);
  const target = tabButtons.find(function (button) {
    return button.dataset.sourceSlug === slug;
  });
  if (target) {
    bootstrap.Tab.getOrCreateInstance(target).show();
  }
  tabButtons.forEach(function (button) {
    button.addEventListener('shown.bs.tab', function () {
      history.replaceState(null, '', '#' + button.dataset.sourceSlug);
    });
  });
});

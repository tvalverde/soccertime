# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Favourites belong to the visitor now.** They were curated in the admin and everybody saw the same ones, so the landing page was one person's agenda. Each visitor picks their own with a star on a team's or a competition's page, and the landing page answers with theirs. **Anyone who chooses nothing sees the same favourites they always did**, from the same shared cache — which is every first visit and every crawler. The one difference is that the landing page paginates at 25 like every other listing; the busiest three-day window in the last 400 days of production data held 24 curated events, so today it never shows a pager at all.
- **The selection is filtered on the server**, carried in a signed cookie. That is what lets the page paginate, and pagination is why the first design was thrown away: filtering in the browser meant shipping the whole window for a script to sift — **437.1 KB against 36.6 KB**, measured on a copy of the production database — and the server would then have been paginating events the visitor never asked for, so their own could land on page three while page one looked empty.
- **No JavaScript at all.** The star is a plain form, its pressed state is `aria-pressed`, and which of the two icons is drawn follows from that in `theme.css`. Nothing to allow in the Content-Security-Policy, and it works with scripting switched off.
- A visitor's own star reads a competition as covering **its matches**, where the curated rule counts a competition only for races and simple events. That asymmetry is right for a hand-picked list, which would be swamped, and wrong for somebody who pressed the star on La Liga's own page. The curated default is untouched and a test pins it.

### Security
- **A form cannot live in a shared cache, and that decided the whole shape.** Rendering `{% csrf_token %}` makes Django set `Set-Cookie: csrftoken`; stored in a cache shared by everybody, that response hands the same token and the same cookie to every other visitor, undoing exactly what the token is for. It is the shape of the per-request message that leaked into the page cache once before, with a security token in place of a notice. So the pages carrying a star are served fresh and marked `private`, the competition listing keeps its cache and its stars off — it is the heaviest page on the site — and two tests assert that **no cached page renders a token or sets a cookie**.
- The visitor's page is never put in the shared cache either. Keying the cache by cookie was rejected: anyone could then mint entries and push the real pages out of a store that holds three hundred. Visitors carrying a selection are simply served fresh, and a test proves a stranger arriving next still gets the curated page.
- The selection lives in a **signed cookie rather than a session row**, so a stranger posting a thousand times leaves nothing behind but their own cookie. Django's session framework is deliberately untouched: switching `SESSION_ENGINE` would have moved the admin login to cookies too, and an auth session that cannot be revoked server-side is a worse thing to own than a list of teams. A tampered or unsigned cookie reads as no selection at all.
- **The star is the only write this site accepts without a login**, so it carries the guards to match: POST only — over GET every crawler walking the site would press it — the entity looked up before anything is stored, a redirect built from that entity rather than from a parameter, so there is no open redirect, `HttpOnly` and `SameSite=Lax` on the cookie, a cap of 50 per kind that bounds the cookie against the browser's 4 KB ceiling and the page against its own length, and a Traefik rate limit on a router of its own — the same mechanism already measured on the admin. The prefix is `/soccertime/favorite/`, one letter away from the landing page it must not throttle.

- **The strips and the gold border follow the visitor too.** The crest and flag shortcuts above every listing, and the border marking a favourite row, read the same selection as the landing page. Leaving them curated would have made a site that contradicts itself: your agenda filtered to your teams, under a strip of somebody else's, beside rows bordered as theirs. The listings pay for it on the same terms as the landing page — **shared cache for everybody who has chosen nothing**, which is every crawler and every first visit, rendered fresh for whoever has chosen something.

### Fixed
- **An unsigned cookie could switch the page cache off from outside.** The decorator branched on a cookie of that *name* rather than on a valid signature, so `Cookie: soccertime_favorites=x` made the server render the ordinary curated page — freshly, on every request, with no rate limit in front of it. **Measured at 1.9-2.3s each on `/competitions/`**, which is half a request a second to saturate the container that also serves the database. It branches on the signature now, which costs one HMAC over a hundred bytes. Found by an audit of this branch, not in production.
- **The pages that left the shared cache were paying an hourly cost per request.** A competition page took **1,608 ms** to list the teams that play in it, because `Q(home_matches=…) | Q(away_matches=…)` makes SQLite join the 52,000-row event table twice and sort the result distinct; asked as two plain lookups it is **19 ms** for the same thirty teams in the same order. The entity pages paginate now as well. `/events/competition/3/` went from **1.64s to 0.028s** end to end.
- **`date__date__gte` wrapped the column in a conversion**, so no index applied and every row was converted before it could be compared. The three places asking which sports and competitions have something upcoming now compare against the instant today began: **585 ms against 8 ms** for the sports listing and **696 ms against 84 ms** for the competition counts, same rows. Built from `localtime()`, and tests pin the boundary — from `now()` it would put midnight two hours late in Madrid and drop an event at 00:30 from a listing that claims to start at the beginning of today. `/competitions/` went from **2.56s to 0.29s**.
- The favourite star's cookie is named for this application and scoped to its path. A bare `favorites` at `/` is sent to every sibling app on the same host, and one of theirs would arrive here.
- **Editing favourites in the admin now shows at once.** Nothing invalidated the page cache when a `Favorite` changed, so the strips went on showing the old ones until the hourly scrape happened to clear the cache for its own reasons — up to an hour of a change that looked like it had not saved. Saving or deleting one clears it now. Coarse on purpose: working out which of eight page variants a favourite appears on is more machinery than a table nobody edits twice a week deserves.

## [0.6.0] - 2026-08-12

The first improvement from the list, and the first release in a while that a visitor can
actually see: the agenda stops opening in the past.

It began at local midnight, so arriving in the evening meant reading what had already
happened — 16 of the first 25 rows were over when this was measured, and on a busy Saturday
roughly 71 of 127 by six o'clock. It opens at the page holding the present now, and what
started in the last two hours is marked as on.

Nothing is hidden to get there, and that is the part worth knowing. Every event stores no
duration at all, so "finished" is always a flat two-hour guess — wrong for the 30% of events
in tennis, cycling, motorsport and golf, where a stage runs five hours. Four different cutoffs
were measured against a real Saturday and every one of them buried events that were still on.
Moving where the listing opens makes that problem disappear rather than shrink: being a page
off costs a click, hiding a match that is on does not.

The badge is decided in the browser for the same reason the times and the favourites were:
pages are cached for an hour, and one rendered with the page would still be claiming an event
is live an hour after it ended.

### Added
- **The agenda opens where the present is, and marks what is on now.** It began at local midnight, so the first thing a visitor read was what had already happened: measured on 2026-08-12 at 16:41, **16 of the first 25 rows had finished** and the first live one sat at position 17. A busy Saturday is worse — of 127 events, roughly 71 are over by 18:00 and 115 by 22:00. The listing now opens on the page holding the present, and rows that started within the last two hours are marked **EN DIRECTO**.
- **Nothing is hidden to achieve that**, and the measurements are why. Every event stores `duration = NULL`, so "finished" is always a flat two-hour default, and **30% of future events are in sports where that is wrong** — tennis, cycling, motorsport, golf: a cycling stage runs five hours. Filtering the past away was measured at four cutoffs and none was safe: two hours buried five live events on that Saturday, and even six buried two at 21:00. Opening on the right page makes the problem disappear rather than shrink — no event can vanish, and being one page off costs a click. Earlier rows stay exactly where they were, one step back.
- The live badge is decided **in the browser** (`live_state.js`, the fourth script alongside the existing three, same-origin and so allowed by the CSP), because every listing is cached for an hour: a badge rendered with the page would keep claiming an event is live up to sixty minutes after it ended. Without JavaScript the row reads exactly as before — the badge is an addition, never the only carrier of something. **Stated limitation**: a cycling stage still running after three hours loses its badge. The rule errs towards silence, never claiming something is live once it is over; claiming wrongly is the worse mistake on a page whose job is telling you what to watch. Per-sport durations were offered and declined — 24 values to estimate and maintain, still wrong for tennis, which ranges from 1.5 to 5 hours.
- The anchor costs exactly one query, counted rather than assumed, on a page cached for an hour.


## [0.5.3] - 2026-08-12

The last five findings of the code review, closed together — which finishes it. Nothing here
is visible from a browser; it is the instrumentation and the small lies that had accumulated
underneath.

The substantial one is the access log. Two health probes were writing 89,280 lines a day
between them, **97% of everything logged**, against a driver that keeps 30 MB — so a genuine
error was pushed out of `docker logs` long before anyone would look for it, and the deploy's
own error check was reading almost pure noise. The probe is filtered out now, but only while
it is passing: a health check answering 500 while the container still reports healthy is
exactly how this site went down twice, so the noise goes and the evidence stays.

Two bugs surfaced while building that, and **neither was caught by a unit test**. Declaring
the filter in Django's `LOGGING` silenced the entire access log, because `dictConfig` resets
a named logger's unspecified keys and so cleared uvicorn's handler. And anchoring the path
match at the start matched nothing in production, because `--root-path` puts
`/soccertime/healthz/` in the line. Sixteen unit tests passed with the log completely broken;
running it against the replica is what showed both. They have tests now.

The rest: a dead template filter deleted, four view signatures corrected, and the deploy's
settle time tied by a test to the probe interval it silently depends on. `collectstatic`
accumulation was measured at 6.4 MB and deliberately left unpruned — adding machinery to the
deploy is not worth reclaiming megabytes that are not scarce — with the size now reported so
the day it matters is visible.

### Fixed
- **The access log is about visitors again.** Traefik probes `/healthz/` every second — which is what lets a deploy hand over between containers without dropping requests — and the container health check adds one every thirty. Measured on production: **89,280 lines a day, 97% of the access log**, against a json-file driver rotating at 10 MB × 3, so a real error left `docker logs` far sooner than it should and `make remote-error-check` scanned mostly probe traffic. (The review had estimated ~170k; the measurement halved it and the proportion is the number that matters.) A filter now drops the probe's line **only while it is passing** — a health check answering 500 is how this site went down twice with the container still reporting healthy, so the noise goes and the evidence stays.
- Four view signatures said `str` where the URL converter has delivered `int` since 0.4.2. mypy passed because the value is only forwarded, so nothing caught the lie; `team_events`, `channel_events`, `sport_events` and `competition_events` now say what they mean. The queryset helpers keep `int | str`, which is honest — the ORM accepts both.

### Removed
- The `env` template filter and its allowlist. Its last caller went with the `DJANGO_DEBUG` branch of `channels_list.html` when the channel column was rewritten, leaving an environment reader reachable from any template with no users at all — a security-sensitive surface earning nothing.

### Added
- A test tying `PROXY_SETTLE_SECONDS` in the `Makefile` to `healthcheck.interval` in `compose.production.yaml`. The five-second settle is five probe intervals, and only a comment connected the two across a file boundary: raise the interval alone and the handover retires the old container before Traefik has accepted the new one, reopening the 404 window 0.5.1 measured shut. Verified by mutation — changing the interval to `2s` turns the suite red.
- `make remote-ps` reports the static volume's size. `collectstatic` accumulates superseded hashed files forever — **6.4 MB in 300 files today**, growing a few KB per deploy that touches a static file, roughly 2 MB a year. Pruning was considered and **deliberately not built**: it would add machinery to the deploy, which is the part of this system that has caused two real outages, to reclaim megabytes that are not scarce. Reporting the size means the day it stops being trivial is visible without anyone having to remember to look.


## [0.5.2] - 2026-08-12

DNS rebinding closed in the image downloader: it vetted a scraped URL's host against the
private ranges, then handed the URL to `requests`, which resolved the name **again** to
connect — nothing forced the two lookups to agree, so a hostile DNS with a short TTL could
answer public to the check and internal to the fetch, reaching a neighbour on `nassut-net`
that is not reachable from outside. The connection is now pinned to the address the check
itself resolved, so the name is never looked up a second time and the internal host never
receives even a TCP handshake. The payoff was only a blind request whose response gets
decoded as an image and discarded, so this closes a real gap in an existing safeguard
rather than a live exploit. Two independent reviews of the fix found nothing to change.

### Security
- The image downloader connects only to the address it vetted, closing a DNS-rebinding hole. It resolved a scraped image URL's host and checked every address against the private ranges, then handed the URL to `requests`, which resolved the name **again** to connect — with nothing forcing the two lookups to agree. A hostile DNS with a short TTL could answer public to the check and internal to the fetch, reaching a neighbour on `nassut-net` (Traefik, the databases) that is not reachable from outside. The name is now resolved once: `_reject_unroutable_host` returns the vetted address, and the connection is pinned to it for the duration of the request through urllib3's `create_connection` hook, so the internal host never receives even a TCP handshake. The hostname still travels for the Host header and TLS SNI, so certificate validation is unchanged — verified live against the real source, and each redirect hop is separately resolved, vetted and pinned. The payoff was only a blind request whose response is decoded as an image and discarded, so this is a bounded gap in an existing safeguard rather than a live exploit — MEDIUM finding of the 2026-08-12 review. Pinned by a test that fails without the pin (the socket goes to the vetted IP, never a second lookup's result), mutation-checked, and covering SNI preservation, redirect hops and IPv6.

## [0.5.1] - 2026-08-12

The code review's findings, closed from the top down — and every one of them was confirmed
by demonstration before it was fixed, which is how two of the fixes found bugs nobody was
looking for.

The deploy relay could report success having deployed nothing: with two containers left by
an interrupted run it mistook the second old container for the new one, and with zero it
started two and seeded that state for every deploy after. It now heals what it finds and
asserts, by image id, that what serves is what was built — exit 0 means deployed. The
rehearsal runs the same script as production, in all four states.

The scraper's ±2-day duplicate window merged real fixtures: an ACB doubleheader on the same
court cannot be told from a duplicate by any window, because closeness is ambiguous by
nature — 99 of the 219 close pairs in the data sit under three hours apart. Identity is
exact now and date changes are observed instead of guessed, per scrape unit, with moves
pruned at once and ambiguity given two consecutive misses. The first real run then caught a
bug on its own: the phase text sat inside race identity and had quietly accumulated 234
duplicate rows in production, visible as doubled listings. All healed, by rule and by a
one-shot migration.

Around them, the smaller closures: every remote target now acts on every container instead
of assuming one; migrations run before the handover, which this very release needed —
it adds columns, and the old order would have served 500s while migrating; and
`docker compose pull` on the host stopped failing over the two images that are built there
and published nowhere.

### Fixed
- **A second fixture of the same pairing can be stored again.** The scraper's ±2-day window treated any event of the same (competition, local, visitor) within two days as the same event and realigned it, so an ACB doubleheader on the same court or an NBA back-to-back collapsed into one row whose date followed the latest scrape: 219 such pairs exist in rows written before the window landed, zero after it. No smaller window helps — 99 of those pairs sit under three hours apart — and the source offers no round number or stable id. Closeness is ambiguous by nature; only what the source lists *today* can tell a duplicate from two real games. So identity is now exact — (competition, teams or name, datetime) — and date changes are **observed, not guessed**: each scrape unit declares what it covered (a sport's agenda, a team's fixtures, the date range it showed), and a stored future event inside that coverage that was not listed is what a move or a cancellation looks like. A move brings its replacement in the same scrape — seen reaching what was already stored — and is pruned at once, at any scrape frequency; anything short of that is an omission or a cancellation, indistinguishable today, and falls only after **two consecutive misses**, counted in successful scrapes rather than hours so the rule keeps its meaning if the frequency changes. A doubleheader lists both rows and is never touched; a page that yields nothing, or dies mid-parse, judges nothing.
- **The phase text was part of a race's identity, and it duplicated events.** `details` ("Liga Regular", "1ª Ronda") sat inside the lookup, so every time the source rephrased it a second row landed in the same (competition, name, instant) slot: **234 such rows existed in production**, rendering as visibly duplicated listings. Found not by reading but by the first real reconciliation run flagging `Vuelta a España Etapa 1` as missing while the page clearly listed it — the listed row was matching a different twin. The text is data now, updated in place; an unseen row whose exact slot a seen row occupies is deleted as a duplicate by definition; and a data migration collapses the accumulated twins once, keeping the freshest, since slots the pages no longer cover would otherwise keep theirs forever.
- **Migrations run before the handover, not after.** The deploy migrated after the new container was already serving, so a migration adding columns the new code reads — this release's is exactly that — would have had every page answering 500 for the seconds between serving and migrating, caught by the deploy's own error gate but caught is not avoided. Migrations now run in a throwaway container while the previous one still serves, which the additive-first discipline makes safe: Django only selects the columns a model declares, so old code is indifferent to new columns. Destructive migrations need a two-release path, which is the standard rule this order enforces.

- **The remote targets stop assuming there is exactly one container.** Sibling of the relay finding, same root: `remote-clear-cache` cleared "the" cache through `compose exec`, but the page cache lives in a tmpfs inside each container, so with two running — mid-relay, or a stuck state — one kept serving stale pages for up to an hour; `remote-scrape` had the same flaw in its trailing cache clear, and now chains the fixed target after scraping once, since the database is shared state and once is the right number of times; `remote-error-check` inspected `ps -q | head -1` and scanned one container's log; and `wait-remote-healthy` ran a `case` over what becomes a multi-line status, so one healthy container declared success while the other was still starting — demonstrated on the replica before fixing, with the old logic answering OK and the new one refusing on the same state. Each now iterates over every container of the service and says which it touched. The migrate step keeps its single `exec` deliberately, with a comment saying why it is safe: the relay's post-condition has just asserted there is exactly one, and the database is shared, so once is also correct.

- **The deploy relay now proves it deployed, or says it could not.** Top finding of the code review, demonstrated before fixing: the relay assumed exactly one container was running, so with two left behind by an interrupted deploy, `--scale=2` created nothing, the "new" container it waited on was really the second old one, and the deploy reported success **with the freshly built image never having run** — and with zero it started two, seeding that exact state for every deploy after it. The logic now lives in `scripts/relay.sh`, one file that production receives over `ssh 'sh -s'` and `make replica-relay` runs against the local replica, so the rehearsal cannot diverge from the real thing — which is how a divergence of proxy versions cost thirteen seconds two days ago. It heals the anomalous states loudly (extras retired newest-kept, zero handled as a cold start) and asserts, **by image id**, that the container left serving runs the image the deploy just built; success now implies deployed. Rehearsed in all four states with the site probed every 200 ms: normal handover 0.0s, the stuck two-container state healed with the rebuilt image verified serving in 0.4s, a cold start, and a missing image aborting with exit 1 while the old container kept serving. A skip-if-same-image shortcut was written and removed: a deploy that only changes `.env.production` produces no new image, and skipping the handover would silently leave the new configuration unapplied.

- `docker compose pull` on the host no longer fails. `soccertime:latest` is built there and published nowhere, so a pull asked a registry for it and got `pull access denied … repository does not exist`, which failed the whole command — the four images that genuinely are remote were fetched, and the command still reported failure. The service now declares `pull_policy: never`, which states what is true and needs nobody to remember a flag. `pull_policy: build` was tried first and rejected although it also silences the error: it makes every `up` rebuild the image, which would put a build, and a `docker/dockerfile:1` download, inside the container hand-over that exists to keep a deploy from interrupting the site.

### Added
- `make remote-pull` refreshes the host's images with `--ignore-buildable`, which skips exactly the services declaring a `build:` — this project's and the neighbouring stack's `frankenshop`, the other half of the same failure and a file this repository does not own. Deliberately not `--ignore-pull-failures`, which would also swallow a real registry outage for the images that matter. Verified against the server: exit 0, both built images skipped, the other four pulled.
- `make remote-pull PULL_FLAGS=` runs the bare command, which is what proves whether the flag is still doing the work or the services now declare `pull_policy: never` themselves. With both halves declaring it — the neighbouring stack's was on `if_not_present`, compose's default under its old name — a plain `docker compose pull` on the host exits 0 with no denial at all: the two built images skipped, the four remote ones fetched.
- `make remote-ps` now reports the compose version and which services would have to be built rather than pulled, which is how both halves of the above were identified.


## [0.5.0] - 2026-08-12

The site starts telling people where the match is on, and deploying it stops interrupting
them.

It had been told, for every one of its 2,148 future events, and threw the answer away for
1,809 of them: the template rendered a channel only when it also had a playable link, so the
column was blank unless you could watch it from here. 952 of those blanks named HBO MAX, DAZN,
Movistar+ — the one fact a television agenda exists to carry. A real page went from showing a
channel on 8 rows out of 25 to showing one on all 25, at 1-2 % more bytes, and what can be
played now comes first inside the row and can be filtered on its own.

The deploy was stopping the container before creating its replacement, which cost about six
seconds of 502 and then 404 every time. It now starts the new one beside the old and retires
the old only once the proxy is sending traffic to the new: measured through a real deploy,
four failed requests out of 553 rather than six unbroken seconds.

That fix went in wrong first and cost thirteen seconds — worse than what it replaced —
because the replica pinned `traefik:v2.11` while the server runs 3.7.10, and version 3 marks a
new server down until it has probed it. The lesson was already written in `CLAUDE.md`: the
states production holds that local does not. The replica's proxy is pinned to production's
now, which reproduced the failure in one attempt.

### Added
- **A deploy no longer takes the site down.** It stopped the container before creating the replacement, so Traefik answered **502 for about 1.5 seconds** while the old one died with its route still registered, then **404 for about 4.5 seconds** once the container was gone and no router matched at all — roughly six seconds, reproduced and measured in the replica by polling every 200 ms rather than taken on trust. The new container now starts beside the one still serving, and the old one is retired only once the new one answers `/healthz/`. Measured the same way afterwards: **0.2 to 0.4 seconds**, one or two requests, at the instant the outgoing container stops.
- Traefik asks before it sends. It routes to a container the moment it starts, without waiting for the process inside to listen, so overlapping alone still lost about 1.2 seconds to 502s split evenly between a live server and a socket nobody was accepting on yet. A load-balancer health check closes that. One detail only a rehearsal finds: the probe carries the container's IP as `Host` unless told otherwise, Django rejects it through `ALLOWED_HOSTS`, every server is marked down and the service answers **503 to everything** — so the hostname is explicit in both files, and a test pins that the replica overrides production's rather than inheriting a name it does not answer to. The interval is 1s because at 2s a newly started container received traffic for up to two seconds before its first failed probe.
- The replica's proxy is pinned to the version production runs. It said `traefik:v2.11` while the server runs **3.7.10**, so the replica was rehearsing a different proxy from the one in front of the site — and the difference was not cosmetic. Traefik 3 marks a newly discovered server **down** until its first probe succeeds, where 2 marked it up and found out later, so retiring the old container the moment the new one answered left the service with no live server: 502, then 503, then the router dropped altogether and every path answered **404**. That cost 13 seconds on the first real deploy, worse than the six it replaced. Reproduced at 2.4 seconds in the replica once its proxy matched, and removed by waiting five probe intervals between "the container answers" and "the old one goes". Rehearsed twice more after that: 0.0s and 0.2s.
- `make remote-ps` lists what is actually running on the server, which is how the version mismatch was found.
- A `retry` middleware was tried and removed: with the relay in place it made no measurable difference, and it is the kind of label whose churn causes the transition below.

- **The agenda names the channel every event is on**, whether or not it can be watched from here. `channels_list.html` rendered a channel only when it had an enabled link and silently dropped the rest — outside `DEBUG`, where they appeared struck through, so the only person who ever saw them was a developer. In production the column was simply empty. Measured on a real page: **25 rows, 8 showing a channel, 17 blank**, and the 8 were exactly the 8 with a play button. Across 2,148 future events, 339 were watchable and shown, **952 named a real channel that was hidden** — HBO MAX, DAZN, OneFootball, Movistar+ — and 857 carried only the `Canal por confirmar` placeholder. A television agenda that has been told where a match is on and does not say so is failing at its one job. The same page now shows a channel on **25 rows of 25**, with the play buttons unchanged at 8.
- Inside a row, the channels that can be played come first. `Channel.Meta.ordering` is alphabetical, which buried the actionable one: an event on ATP Tennis TV and Movistar Plus+ listed the channel without a link ahead of the one carrying the play buttons. Sorted over the list `with_related()` has already prefetched, so it costs no query — a test asserts zero. The muted badge is also italic, which reads as a qualifier. Strikethrough was considered and rejected: it means *cancelled*, so a struck-through DAZN would say the match is **not** on DAZN, the opposite of the fact this change exists to surface. It was right in the old `DEBUG` branch, where it meant "the template dropped this", a statement about code rather than about the world.
- A filter for what can actually be watched, `/agenda/?watchable=1`, as a two-state control beside the datepicker. Both counts are scoped to the date and search already applied, so they always describe the list underneath rather than contradicting it. One identifier rather than a hyphen because `{% querystring %}` parses its keys as Python names, and it matches `EventQuerySet.watchable()`.

### Fixed
- The channel column's markup depended on an **environment variable**, not on settings: `{% if 'DJANGO_DEBUG'|env %}` meant the suite exercised a different template than production rendered. A test asserting the column's contents passed in the development container and failed with `DJANGO_DEBUG=false`, where the cell came back literally empty. The branch is gone, so there is one template for everyone.


## [0.4.4] - 2026-08-11

Nothing a visitor can see. This is the tooling around the site, and every item in it was
found by being bitten during the day's two releases rather than by looking for it.

The deploy could not read its own logs. `CLAUDE.md` requires checking them for 500s after
every deploy and, in the same breath, that production operations live in the `Makefile` and
not in an ad-hoc SSH command — and no target read logs, so the two instructions could not both
be obeyed. Verification of the 0.4.2 deploy had to fall back on fetching pages and inferring.
A deploy now fails outright when the container it just started has logged a 5xx.

The local production replica had three ways of lying about itself: it silently overwrote the
development image, so `make test` died with `executable file not found` at the worst possible
moment; it answered 404 on every path when a variable nobody mentions was unset, which reads
as a broken application rather than a proxy with nothing to match on; and it refused every
write to a database volume it did not own. All three are fixed where they start, so the
command in the README works exactly as written with nothing exported and nothing prepared.

### Added
- `make remote-logs` reads the application's log, with `SINCE`, `GREP` and `TAIL`. `CLAUDE.md` requires checking production's logs for 500s after every deploy and, separately, that production operations live in the `Makefile` rather than an ad-hoc SSH command — with no target that read logs, the two instructions could not both be obeyed, and the evidence that nothing was throwing had to come indirectly from fetching pages.
- A deploy now fails if the new container logged a 5xx since it started. Five pages answering 200 is not proof a release is clean, and this deploy has twice reported success over a broken site. The window is deliberately narrow: widen it and unrelated crawler traffic decides whether a deploy passes. The offending lines are printed rather than counted, because whether a 5xx matters is a judgement a person makes. Exercised by pointing it at 2xx, where it correctly found the traffic that is certainly there and failed — a check that cannot fail is worth nothing, and a mis-escaped pattern would have passed silently forever.

### Fixed
- **The local replica's two traps, both of which look like the application is broken.** `TRAEFIK_HOST_RULE` is absent from `.env`, the only file compose interpolates from, so the documented command produced an empty router rule and **Traefik answered 404 to every path** — including a valid team id, which is what makes it read as a Django problem rather than a proxy with nothing to match on. The replica now spells its own rule out in `compose.production.local.yaml`, so nothing needs exporting; `compose.production.yaml` keeps the variable untouched, since the server includes that file. And the replica's database volume comes from a production copy, so it belongs to production's UID while `.env` sets this machine's — 1000 against 1001 — and any write failed with `attempt to write a readonly database`, which says nothing about ownership. `make replica-migrate` reads the owner off the file instead of hardcoding a number that changes with whichever dump was loaded. Verified by running the README's command verbatim with nothing exported and nothing prepared: three pages at 200, a migration applied, and the development container untouched.
- The local production replica builds `soccertime:replica` instead of a second image under `soccertime:latest`. Bringing that stack up builds **both** `web` and `soccertime-web` in one command, with opposite values of `INSTALL_DEV`, and both wrote the same tag — so which image ended up there depended on which build finished last. Not theoretical: it happened while closing 0.4.3, when the development container came up on a production image and `make test` died with `exec: "pytest": executable file not found`, a message that reads as a broken environment rather than a tag collision. The reverse is quieter and worse — start the replica without `--build` and it runs an image carrying the test and lint toolchain, so the rehearsal stops rehearsing what it exists to rehearse. The separation is now visible in `docker images`: 220 MB against 331 MB. Reproduced the exact sequence afterwards to confirm it: building the replica leaves the development image untouched, and the replica's own image still has no pytest. Four tests parse the compose files — with `re`, as `test_requirements.py` already reads the Dockerfile, since a parser is not worth a dependency for four fields — and assert that no tag is claimed twice and that the replica still builds without the toolchain. `docker image prune` is unaffected: it removes untagged images only, so the new tag survives.
- The replica stack no longer starts the development server. It is `compose.yaml` plus overrides, so it inherited the `web` service and brought up a second Django on port 8000 on every `up` — which is also what put two builds behind one command and made the tag collision above possible. It is profiled out in `compose.production.local.yaml`, which is compose's way of saying “defined here, not started here”; declaring the profile in `compose.yaml` instead would have been the obvious mistake, since a plain `docker compose up` would then start nothing at all. Confirmed by running it and not only by reading the file: with an already-running development container, bringing the replica up leaves it untouched rather than recreating it, and both stacks serve at the same time. The replica now starts three services and builds one, where it started four and built two.

## [0.4.3] - 2026-08-11

The stored times stop lying, and nothing on the site moves.

Every event was stored as Spanish wall clock wearing a UTC label, and rendered in UTC, so the
two errors cancelled and the page was right. Nothing compared against the real clock was: the
front page held 111 events with 7 of them already over, because a window declaring three hours
retained five in summer and four in winter.

Shipped as two releases' worth of care in one day but two separate deploys, because the fix
has two halves that cancel each other and landing one without the other shifts every time on
the site. The first deploy changed only how the templates read a datetime and was verified by
confirming that nothing changed; the second moved 52,133 rows, the setting and the scraper
together. Production was compared before and after each: **233 events across ten dates in both
seasons, none of them moved, and every day header identical**. That comparison is also the
proof the migration ran — one half alone would have shifted the whole site by two hours.

The offset came from each event's own date rather than a constant, since the catalogue splits
28,689 summer against 23,444 winter and the scraper writes fixtures months ahead of the
changeover. The one visible consequence is intended: events now leave the front page about two
hours sooner, which is what `hours_before=3` always claimed.

`TODO.md` had recorded that fixing `TIME_ZONE` would shift every displayed time by two hours.
It would have done nothing at all — the templates called `.time`, which discards the zone
before formatting — and that correction is what determined the order of the two deploys.

### Fixed
- **Event times are stored as real UTC.** The scraper called `make_aware(value, get_current_timezone())` under `TIME_ZONE = "UTC"`, which applies no offset at all, so a 22:00 kick-off was stored as `22:00 UTC` — the right number wearing the wrong label. Rendering in UTC printed it back unchanged, which is why the site looked correct while everything compared against `timezone.now()` was out by the offset. Measured on production: the front page held **111 events of which 7 had already finished**, because `in_window(hours_before=3)` retained events for five real hours in summer and four in winter, never the three it declares. It now retains three: the oldest event on the replica's front page started 2h46 ago and the one that finished longest ago finished 46 minutes ago, which is what three hours from kick-off means with a two-hour default duration. The 52,133 rows were converted with the offset taken from **each event's own date** rather than a constant — production splits 28,689 summer against 23,444 winter, so a single subtraction would have put nearly half the catalogue an hour out — and the migration has an exact inverse, verified in both directions including October's repeated hour. `TIME_ZONE` is `Europe/Madrid` and the scraper now names `Europe/Madrid` explicitly, so it reads an announced time as Spanish screen time whatever the setting says and whatever month the scrape runs in.
- `today_onwards` built midnight with `timezone.now().replace(hour=0, …)`, which is midnight **UTC** — 02:00 in Madrid. For the two hours after midnight the site's idea of today was still yesterday, so an event at 00:30 fell outside a listing that claims to start at the beginning of today. That one was wrong under either scheme. The same applied to `Sport.with_events`, the favourite competitions, the competitions page and the datepicker's upper bound, all of which took the UTC date; they take the local one now.

### Changed
- The agenda renders the event's datetime instead of its `.time` and `.date`, which is a prerequisite for fixing the stored times and, on its own, changes nothing at all. `.time` returns a naive `datetime.time`, so the value reached the formatter with its zone already discarded: the page was deaf to `TIME_ZONE`, rendering the same string under `UTC` and under `Europe/Madrid`. That is precisely the state in which moving the stored data to real UTC would shift every time on the site by an hour or two without any test noticing. Nothing in the suite asserted a rendered time, so five now do — three of them failing before this change, printing 20:00 for a summer event at 22:00 Madrid, 21:00 for a winter one, and filing a 00:30 event under the previous day. Verified against production data rather than assumed: 287 events across ten dates spanning both seasons, rendered by the old templates in production and the new ones in the local replica, produce **zero differing times and identical day headers on all eighteen pages**. The three pages that differed at all did so because the replica's snapshot holds a different event, not a different time.

## [0.4.2] - 2026-08-11

Two defects that had been live in front of every visitor, found by asking which of the
recorded improvements were actually bugs rather than missing features.

The first wrote server errors into the log for anyone who mistyped a URL: all four event
routes accepted any text where an id belongs and handed it straight to a primary key
lookup, so `/events/team/abc/` answered 500 while `/events/team/99999999/` correctly
answered 404. The test that would have caught it was one parameter away from a test that
already existed — which is the general lesson, not the fix.

The second was the search box ignoring competitions and sports entirely, so "LaLiga",
"Fórmula 1", "Copa del Rey" and "Tenis" all came back empty while "Real Madrid" returned
809 results. They return thousands now, at no cost: the tables were already joined.

It also carries the tripwire left behind by the abandoned Django 6.1 upgrade, so the next
attempt fails in the suite rather than in the admin.

The naive timestamps are deliberately untouched and remain the next thing to fix.

### Fixed
- Every parameterised event route answered **500** for a non-numeric id. `urls.py` declared `<str:team>` and the view handed it straight to `get_object_or_404(Team, pk=…)`, so Django raised `ValueError: Field 'id' expected a number but got 'abc'`, uncaught, and the request became a server error. Measured against production before the fix: `/events/team/abc/`, `/events/channel/abc/`, `/events/sport/abc/` and `/events/competition/abc/` all answered 500, while a numeric id matching no row correctly answered 404. A crawler, a link truncated in a chat or a typo reached it, and each one wrote a server error into the log — which is the place you read when something real has broken. The routes declare `<int:>` now, so a segment that is not a number never matches and the view is never entered. Nothing that exists stops resolving: all seven templates build these URLs from `.pk`. Why it survived is one parameter away from a test that was already there — the existing checks assert 404 using `args=[99999]`, so they cover the shape that worked.
- The search never looked at the competition or the sport, which made the box useless for the most obvious things anyone types. Against the real database: **"LaLiga" returned 0 results, "Fórmula 1" 0, "Copa del Rey" 0 and "Tenis" 0**, while "Real Madrid" returned 809. They now return 1,040, 263, 243 and 6,884. Both new fields are foreign-key hops, so no row can match twice and no `distinct()` is needed — confirmed by counting queries on `/agenda/?search=…`, which is 10 before and after, since `with_related()` already joins them. Channel is deliberately left out although "DAZN" would match 10,494 rows: it is a many-to-many, so it needs `distinct()` and would change the query shape underneath the pagination added this same day, and channels already have a page of their own. The bound added in 0.4.1 still applies unchanged — the new fields are `CharField(max_length=255)` too.

### Removed
- `Competition.has_events` and `Competition.events_count`, referenced from nowhere in the application — not a template, not a view, not the admin. Both walked `self.events.all()` and filtered in Python, so they would have become an N+1 the moment a listing used one. Four tests went with them, which is the only thing that had been keeping them alive.

### Added
- A test that fails when Django moves ahead of `django-admin-sortable2`. The package swaps the admin's `actions.js` for a patched copy named after the running Django, ships one per version up to 6.0, and has nothing for 6.1 — so under `ManifestStaticFilesStorage`, which production uses, the sortable changelists ask for a file nobody shipped and a missing static file raises rather than answering 404. Found while attempting the 6.1 upgrade in a disposable image: with production's own settings, `/admin/soccertime/sport/` and `/admin/soccertime/favorite/` both answered 500 on 6.1 and 200 on 6.0.8, while `/admin/soccertime/team/`, which is not sortable, was unaffected. Nothing already in place would have caught it — the suite runs with `DEBUG=true` where `{% static %}` validates nothing, `collectstatic` succeeds because the file is absent rather than broken, the smoke test never opens the admin, and production keeps the admin switched off, so the deploy would have gone green and the 500 would have surfaced at the next `make remote-admin-on`. The upgrade was abandoned and nothing in the repository was changed for it; `TODO.md` records what was verified clean, so it need not be redone.

## [0.4.1] - 2026-08-11

The security audit is closed. Every finding it raised is fixed and deployed, and this is the
release that took the last of them out — all internal, none of it visible from a browser.

Two of these are worth more than their grading suggests. The image used to default to debug
mode with a hardcoded key, so production was safe only for as long as an unversioned file
kept saying otherwise; it now refuses to start instead, which turns a leak into a 404. And
the deploy runs Django's own deployment checks before recreating the application, so a
security setting that quietly went missing stops the release while the previous container is
still serving — that covers the whole class of downgrade no baked default can reach, since
the right value for HSTS or an SSL redirect depends on where the image is deployed.

The rest is housekeeping that had been earning interest: a production image carrying the
test and lint toolchain, down from 374 MB to 217 MB; the one dependency without a version,
which turned out to be the parser the scraper depends on and was sitting where it looked
like a development tool; and a search box that would run `icontains` across four joined
tables for a string too long to match anything.

### Security
- The image defaults to what is safe, and development opts in. The Dockerfile baked `DJANGO_DEBUG=true` and `DJANGO_ADMIN_ENABLED=true`, so production was safe only for as long as `.env.production` kept overriding them — a file deliberately kept out of the repository, and therefore one that can lose a line with nothing noticing. Demonstrated against the built image: with the old default it came up with debug on and `SECRET_KEY` set to the hardcoded `dev-only-insecure-key-not-for-production`, which makes forging a session trivial; with the new one it exits 1 and refuses to start, so the health check fails, the proxy withdraws the route and the site answers 404 rather than handing out its own configuration. Neither environment changes: `.env` and `.env.production` both set every one of these explicitly, so only the day one goes missing is different. One consequence worth knowing: `docker run soccertime:latest python manage.py …` now needs a `DJANGO_SECRET_KEY`, which is what failing closed means.
- A deploy is gated on Django's own deployment checks. Flipping defaults cannot cover `SECURE_SSL_REDIRECT`, `SECURE_COOKIES` or the HSTS settings, because the right value depends on where the image is deployed and they already default to off — drop one from `.env.production` and the site quietly serves without it. `check --deploy` catches every one of them, so `deploy-production` now runs it with `--fail-level WARNING` in the throwaway container, before the application is recreated: a downgraded configuration stops the deploy while the previous container is still serving, rather than being reported once the new one is live. `make remote-check` gained the same flag so both say the same thing. Verified both ways against the local production replica — exit 1 with the flags missing, clean with them set — and it caught, unprompted, the 20-character key in `.env.production.local` that `TODO.md` already lists as a Low finding.
- Tests pin both halves. The settings ones assert that an absent `DJANGO_DEBUG` leaves debug off, that no key and no debug refuses to start rather than falling back, and that the development key needs debug turned on deliberately. A separate one parses the `Dockerfile` — unusual, and the only thing that pins this: every other test in the suite runs with `.env` loaded, so all of them would go on passing if the image quietly went back to defaulting to debug.
- The production image no longer carries the test, lint and type-checking toolchain. One `requirements.txt` described both environments, and development and production share an image, so deleting the block would have broken `make test`, `make lint` and `make typecheck`. It is a build argument instead: `compose.yaml` asks for the toolchain, a build that says nothing is a production build, and a development image built without it fails on the first `pytest` — neither direction can go wrong quietly. 374 MB down to 217 MB, and no known vulnerability either way; this is surface that was not earning its place.
- `lxml` is pinned, at 6.1.1, and lives with the production dependencies. It was the one unpinned line, so a rebuild could silently change the HTML parser the scraper depends on with no record of what had been tested. Its old position — bottom of the file, below the tooling, no version — also made it look like a development dependency, which is the mistake this split invited: `futbolenlatv.py` asks BeautifulSoup for it by name, so getting that wrong would have left the site serving perfectly while every scrape failed. A test now asserts both, and that every line in both files is pinned, which is the general form of the finding rather than a fix for the one line.
- The local production replica pins the same argument off. Compose merges `build.args` across files, so it would have inherited the toolchain from `compose.yaml` and quietly stopped being a rehearsal of production — checked by listing packages in the running replica rather than by reading the file.
- `/agenda/?search=…` is bounded by what the fields can hold. Not a policy about how much anyone may type: `icontains` asks whether the query is a substring of the value, so a string longer than a `max_length=255` field cannot be inside any of them and the exact answer is nothing. It is now returned without touching the database, where before an arbitrarily long string ran `icontains` across four joined tables in SQLite with a guaranteed cache miss. Truncating was considered and rejected — it would answer a different question than the one asked. The longest name actually stored across 52,133 events is 44 characters.
- The replica's secret key is regenerated at 64 characters, from 20. It was the last thing failing `check --deploy --fail-level WARNING` there, so the replica now passes the same gate production does — which is the point of having one.

## [0.4.0] - 2026-08-11

A minor rather than another patch, because for the first time in this series a visitor can
see the difference: the search hides behind a magnifier on anything narrower than a laptop,
and the pagination control is a different shape. The four releases before it were security
work nobody was meant to notice.

It started as a Content-Security-Policy, which the site was the last one missing. Django 6.0
ships that natively, so the work was not adding a header but earning the right to a strict
one: a nonce cannot function here, because every page is cached for an hour and a cache hit
would pair a fresh nonce with a stale body, so the inline scripts and styles had to leave
the templates altogether and Bootstrap had to come off the CDN. The policy carries no
`unsafe-inline` anywhere.

Deploying that broke the site twice, in two different ways, and both taught something the
project did not know. Stylesheets were served under names that never changed, so the pages
arrived without their inline styles while browsers kept the previous CSS — fixed by putting
a content hash in every static filename. Then the manifest that maps those names turned out
to be read once per process, and `collectstatic` was running after the application started,
so every page answered 500 while `/healthz/` stayed green and the container reported
healthy. Both are now recorded in `CLAUDE.md`.

Asking whether `django-bootstrap5` still earned its place turned up that one of its two tags
renders nothing here by design and the other was dropping the search when you paged, which
is why the package is gone and the pagination is written out. And asking whether a deploy
would need a forced reload turned up that `cache_page` was telling browsers to keep every
page for an hour — so a scrape never reached anyone who had just been on the site.

### Security
- A `Content-Security-Policy`, with no `unsafe-inline` and no `unsafe-eval` in any directive: `default-src 'self'` with `object-src`, `base-uri` and `frame-ancestors` at `'none'`, `form-action 'self'`, and `data:` allowed for images only, because the favicon is an inline SVG. It is the layer that contains an injection rather than preventing one — what would have limited the stored XSS fixed in 0.3.2 — and the site had every other security header and not this one. Django 6.0 ships CSP natively, so nothing was added to `requirements.txt`.
- No nonce, and that is the design rather than a shortcut. Every public view is cached for an hour, and `cache_page` stores the response inside the view decorator, before the CSP middleware adds the header; on a cache hit the header would carry a freshly generated nonce while the cached body still carried the old one, so every inline script would be blocked for everyone except whoever happened to populate the cache. The same shape as the `messages`-in-a-cached-page bug already recorded in `CLAUDE.md`. So the inline went away instead: two script blocks became `teams_toggle.js` and `tooltips.js`, two style blocks and eleven `style="…"` attributes moved into `theme.css` as classes, and the pages now need no permission to run anything.
- Bootstrap 5.3.3 is served from this origin instead of `cdn.jsdelivr.net`. Listing that host would let a tag injected by an XSS pull any package it hosts: the SRI on the tags django-bootstrap5 emits protects the files this project asks for, not the ones an attacker would ask for. The vendored copies were verified against the SRI hashes django-bootstrap5 publishes, and those hashes are recorded next to the tags in `base.html` so the files stay checkable. The package itself went too, later in this release, once the pagination stopped needing it.
- Tests pin the header and every directive, and assert that no public page renders an inline script, a style block, a style attribute or an event handler. That last part is what stops the policy quietly becoming a lie: under it a `style="…"` added in a hurry is ignored by the browser, and the symptom looks like a styling bug rather than a security one.

### Fixed
- A scrape now reaches people who were just on the site. `cache_page` announces its own timeout to the client, so every page went out with `Cache-Control: max-age=3600` and a visitor who had loaded one kept serving it from their own cache for the next hour without contacting the site at all. The scraper would run, `make remote-scrape` would clear the server cache, and none of it arrived — on a listing of live events, where a channel being confirmed is the whole point. A deploy took just as long to become visible. `cached_page` keeps the server cache and drops only the browser's licence to skip the request; `ConditionalGetMiddleware` answers the revalidation with a 304 and no body. Measured against the production-like stack: 304 and 0 bytes instead of 59 KB, with the server cache still turning a 74 ms first request into a 15 ms second one.
- The page cache timeout is read per request instead of when `views.py` is imported. Binding a setting at import is the usual Django footgun — nothing can change it afterwards, which is also why no test could switch the server cache on to check it was still there. That test exists now.
- Paging a search keeps the search. `{% bootstrap_pagination %}` built every link as a bare `?page=N`, so following page two of `/agenda/?search=Real` returned the whole unfiltered agenda — silently, because the page looks perfectly normal and only the rows are wrong: 33 results, a page-two link that served 27 rows of everything, where the 43 that were wanted sat behind `?search=Real&page=2`. The tag could not be told otherwise either; in 26.1 it accepts `pages_to_show`, `url`, `size` and `justify_content`, and nothing for the rest of the query string. A partial built on Django's `{% querystring %}` replaces it, with the gaps between page numbers coming from `Paginator.get_elided_page_range` rather than counted by hand.
- The control gained what the tag did not offer: a wrapping `<nav aria-label>`, previous and next rendered `disabled` at the ends instead of as links to nowhere, and `aria-current` on the page you are on. The wrapper moved inside the partial, so a listing that fits on one page renders nothing at all rather than an empty padded div. One visible change: the old widget showed a fixed eleven pages and put the ellipsis last, so it never revealed how many pages there were — an agenda that looked twelve pages long is eighty-seven. The replacement always shows the first and last.
- Page links are large enough to tap on a phone. Bootstrap's default comes out around 30px, under the ~44px a finger hits reliably, on a site that carries a bottom nav precisely because it is used on one. Confined to the narrow breakpoint.
- Static filenames carry a content hash outside development. Without one, a deploy only reaches browsers that happen to ask again: nginx sends no `Cache-Control` for these files, just an ETag and a Last-Modified, so browsers cache them heuristically under a URL that never changes. Moving the styles out of the templates and into `theme.css` was the first change where that mattered — pages arrived without their inline styles while the browser kept serving the previous stylesheet, and the site looked broken until a forced reload. Bootstrap's source maps are vendored alongside it now, since the storage rewrites `sourceMappingURL` references and `collectstatic` fails on one it cannot resolve.
- `collectstatic` runs before the application is recreated rather than through `exec` afterwards. The manifest that maps plain names to hashed ones is read once, the first time a template renders a `{% static %}` tag, so collecting afterwards let the new process read a manifest that was missing or half-written and then hold it for its whole life. That took the site down for the length of one deploy: every page answered 500 while `/healthz/` stayed green, because it renders no template, so the container reported healthy with the site broken and only the smoke test noticed. Collecting first removes the window instead of covering it with a second restart, which would have meant a burst of 500s on every deploy.
- The header search no longer wraps onto a second line, and exists again below 992px. It was shown from `lg` with `d-none d-lg-flex`, but the container it sits in is 960px until `xl` and the logo and menu take 605px of that, so between 992 and 1199 it dropped under the logo — on every page, the header being shared. Below 992 it is now behind a magnifier, because there is genuinely no room for the box: at 768-991 the container is 720px and about 115px of it is free. Bootstrap's own collapse does the revealing through `data-bs-toggle`, a data attribute its script reads rather than an inline handler, so it needs no script of ours and no exception in the policy. From 992 the box is inline as before, narrowed to the space that is actually there. Checked at 390, 600, 900, 992, 1100, 1199, 1200 and 1400, open and closed.
- `make screenshot` honours `SIZE`. The usage line and `make help` both documented it while the recipe read `SCREENSHOT_SIZE`, so every capture came out at the default width — found when a mobile and a desktop reference shot turned out byte-identical.

### Removed
- `django-bootstrap5`. With the pagination replaced it supported only `{% bootstrap_messages %}`, which renders nothing here and never can: `CLAUDE.md` rules the messages framework out because these views are cached as a whole and a per-request message would be baked into the shared page cache and served to everybody else — `empty_state()` exists for exactly that reason. Removing it also removes `{% bootstrap_css %}` and `{% bootstrap_javascript %}`, which emit the `cdn.jsdelivr.net` tags the CSP work had just moved away from and which would otherwise sit one autocomplete from undoing it.
## [0.3.5] - 2026-08-11

Two places where the site trusted input it had no reason to trust. Django was told to read
the hostname out of a header and to accept whatever hostname it found; the image fetcher
took a URL out of scraped HTML and accepted whatever came back — any address, any size, and
a filename extension chosen by whoever served the file.

Both were demonstrated against the running system before being changed rather than argued
from the code. A request carrying `X-Forwarded-Host: evil.example` was answered 200, and an
SVG payload handed to the previous `save_image` was written into the media volume as
`<sha1>.svg` with `None x None` dimensions, ready to come back as `image/svg+xml` from this
site's own origin. Neither had been exploited: the 2802 images in production are all
legitimate WebP, the largest of them 1322 bytes.

The tightening is the kind that breaks things quietly if it is done from the outside in, so
each guard was checked against what production actually does. `localhost` had to stay in
the host list because the container's health check does not pass through the proxy, and a
tidier list would have taken the site down while the application answered every real
request correctly — the same failure this project already had once from
`SECURE_SSL_REDIRECT`, and now the subject of a test. The image guards were run against the
real source, and then against production itself by deleting a stored flag and watching it
restore byte-identical.

### Security
- Images fetched from scraped pages are bounded and vetted. `download_image` accepted any scheme, any address, any size and any content: it read `response.content`, which pulls a whole body into memory however long it is, inside a container capped at 512 MB, and let `requests` follow redirects without looking at where they led — from a container sharing a network with Traefik and every other service on the host. It now refuses a scheme outside http/https; follows redirects one at a time so each hop is checked, since letting the library follow them is exactly what would undo an address check; rejects any host resolving to a private, loopback, link-local or reserved address, checking every record a name returns rather than only the first; rejects a declared or actual body over 2 MB, against a largest-image-in-production of 1322 bytes; and applies an overall deadline, because the existing 10-second timeout is per read and a slow drip resets it forever.
- The stored filename no longer comes from the source URL. `save_image` took the extension from the URL, so whoever served the file chose how nginx would later label it — and Django never objected, because `get_image_dimensions` answers `(None, None)` for content it cannot parse instead of raising. Demonstrated against the previous code before fixing: an SVG payload was written into the media volume as `<sha1>.svg`, dimensions `None x None`, raw script on disk, ready to be served back as `image/svg+xml` from this site's own origin and to run on the first direct visit. Both halves of the name now come from the content — sha1 for the stem, and the format Pillow decodes for the extension, checked against an allowlist that deliberately excludes SVG. The content type is treated as a cheap early-out rather than as evidence, since it is only the remote server's claim.
- The image request bypasses the shared HTTP cache. `scrapit` reaches `requests_cache.install_cache()` before any image is fetched, and a cache reads whole bodies in order to store them, which would have left the new size limit doing nothing. Nothing is lost: both callers already skip the download when the file is present in storage.
- Verified against the real source rather than only in tests. All 228 flag URLs serve `image/webp` at a few hundred bytes and pass every guard. After deploying, a flag's file was deliberately removed from the production volume and restored through the new path: the same content hash, the same `.webp` name, the same 32×32 dimensions, and the volume back to 2802 files. What this does not fix is DNS rebinding — the address is checked and then resolved again by `requests`, and closing that gap means pinning the IP and setting the `Host` header by hand, which is more machinery than this earns here.
- Production validates the `Host` header again. `DJANGO_ALLOWED_HOSTS` was `*`, which turns the check off entirely, while `DJANGO_USE_X_FORWARDED_HOST` tells Django to take the host from a header rather than the connection. Demonstrated against the running site before changing anything: a request carrying `X-Forwarded-Host: evil.example` was answered 200, and the same request now answers 400. Traefik only routes the two real hostnames, so this was defence in depth rather than an open door — but it is the layer that catches the day the proxy rule is loosened or something reaches the container directly, and responses are cached for an hour, which is what turns one poisoned absolute URL into everyone's problem. The list is now `www.mojon.es,mojon.es,localhost,127.0.0.1`; both public names are there because Traefik routes the bare domain too and it does not redirect.
- `localhost` in that list is not decoration, and there are tests saying so. The container's health check does not go through the proxy — it asks `http://localhost:8000/healthz/` directly — so the tighter-looking list of just the public hostnames makes Django answer it 400, the container is marked unhealthy, and the proxy withdraws the route: the site goes down while the application is answering every real request correctly. That exact outage has happened here before, from `SECURE_SSL_REDIRECT`, so one test now asserts the health check's host is accepted and another asserts that dropping it breaks the check.

### Added
- `make remote-apply-config`, which uploads `.env.production` and recreates the container. The admin targets already carried that logic inline. Recreating rather than restarting is the part worth naming: a container keeps the environment it was created with, so a restart reports success and changes nothing.

## [0.3.4] - 2026-08-11

The admin stopped being a permanent fixture of the site. It was the one route answering
to a password, facing the whole internet with nothing slowing down a guess, and an IP
allowlist — the obvious protection for a login form — was ruled out by a fact about the
operator rather than about the code: there is no fixed address to allow. So the route is
simply absent, opened by a make target when there is work to do in it and rate-limited
while it is open. Pinning the flag that governs it then turned up that the admin tests
had been passing on an accident, inheriting a routed admin from the container image while
production ran with it off.

### Security
- The admin is no longer among the site's URLs. `DJANGO_ADMIN_ENABLED` already decided whether `urls.py` registered it, and production now runs with it off, so `/soccertime/admin/` is a 404 instead of a login form facing the whole internet with nothing slowing down a guess. `make remote-admin-on` and `make remote-admin-off` open and close that window. They edit the local `.env.production` and upload it rather than editing the copy on the server: the deploy uploads the local file, so a server-side toggle would be undone by the next deploy — and undone in the direction that re-exposes the admin, which is the failure nobody would notice. Both directions were exercised against production and the public pages were confirmed serving throughout. An IP allowlist was considered first and rejected, because there is no fixed address to allow.
- A rate limit in front of the admin, for the windows when it is open: 30 requests a minute with a burst of 15, charged per source address. It rides on a Traefik router of its own so it applies to the admin and to nothing else, and that router carries a higher priority than the application's, which would otherwise match the shorter `/soccertime` prefix first. Traefik terminates TLS here with no CDN in front, so the address it sees is the client's and no `ipStrategy.depth` is needed. Verified live: 40 rapid requests to the login page returned 19 × 200 and 21 × 429, while `/agenda/`, `/competitions/` and `/channels/` answered 200 immediately afterwards. Rejection happens in the proxy, so a refused attempt costs no worker and no write to the SQLite file that is also serving the site.

### Fixed
- The admin tests no longer depend on the environment the suite happens to run in. They reverse `admin:` URLs, which `soccertime.urls` registers only when `DJANGO_ADMIN_ENABLED` is true — so they were passing on an accident, the image baking that flag as `true`, while production runs with it off. Running the suite the way production is configured failed six tests with `NoReverseMatch`, which was confirmed before changing anything. The admin patterns are now separable from the rest, and those tests point at a URLconf that always routes the admin, stating the dependency instead of inheriting it. The whole suite passes with the flag true, false and absent.
- The flag itself is now pinned by tests, which nothing covered: it decides whether the admin is reachable at all, and it fails closed, so `1`, `yes`, `on` and a trailing space all leave the admin unrouted. One test asserts that turning it off removes the admin route and changes nothing else about the site.

## [0.3.3] - 2026-08-11

A secret that was never published, and the housekeeping that keeps it that way. The image
carried `.env.production` because `.dockerignore` matched one filename rather than the
family, and the copy inside it was never read by anything. What made it worth acting on
was not exposure — the investigation looked for a way the key could have left the two
machines that build the image and found none — but persistence: four superseded images on
the development machine were still holding the file, so the key had outlived every
deletion anyone would think to perform. It was rotated on that basis, every copy was
removed, and two prune targets now stop superseded images from accumulating unnoticed
again. Both are scoped by a label on the image rather than clearing everything untagged,
because either machine also holds images that other projects built and no registry could
give back.

### Security
- `.env.production` — which holds `DJANGO_SECRET_KEY` — is no longer copied into the Docker image, and the key it carried has been rotated. `.dockerignore` listed `.env`, and that pattern matches only that exact name, so `COPY . .` took `.env.production` and `.env.production.local` into every build; the entry is now `.env*`. Removing them changes no behaviour, because the copy inside the image was never read: the container takes its environment from the compose `env_file`, which is resolved on the host. Nothing indicates the key ever left the two machines that build the image — the project contains no `docker push`, registry or `docker save`, `git log --all -S` finds the key in no commit, and the deploy archive is `git archive HEAD`, which carries tracked files only. What the finding really cost is durability: four superseded images on the development machine were each found still holding the file, so the key outlived every deletion that would occur to anyone. It was rotated on that basis rather than because it is known to be exposed, and those images were removed. The replacement is 64 characters against the previous 52. Rotation invalidates signed data, which here is only the admin login: favourites are rows in the database and no view touches `request.session`.

### Added
- `make prune-remote-images`, which drops this project's superseded images from the production host and now runs at the end of `deploy-production`, after the smoke test — so a deploy that fails never reaches it. It filters on an OCI label carried by the image instead of being a blanket `docker image prune`: three of the untagged images on that host have no `RepoDigests`, meaning another service built them there and no registry can hand them back. The deploy also tags the outgoing image `soccertime:previous` before building, keeping exactly one rollback, because rebuilding from the same commit does not reproduce an image — `python:3-alpine` and pip both resolve afresh, which is how Pillow and Django drifted five releases out of date here.
- `make prune-images`, the same housekeeping for the development machine, where every `up --build` leaves the image it replaced untagged. It filters on the same label, which matters more here than on the server: this machine carries images for unrelated projects. No `:previous` is kept, because locally the way back is to build again and nothing is serving traffic meanwhile. Verified by building a superseded image of each kind and confirming the target removes the one carrying this project's label and leaves the other untouched.

## [0.3.2] - 2026-08-11

A security audit of the dependencies and the codebase, and the three findings that were
serious enough to fix the same day. Two were versions left behind — one of them in the
library that parses images fetched from the internet — and the third was a validator that
had been written for exactly this purpose and never ran, because Django does not invoke
field validators from `save()`. Nothing here is known to have been exploited, and the
production data was audited before each fix: no dangerous link was ever stored.

### Security
- A channel link whose scheme is not on the allowlist can no longer be stored, nor rendered if it is already stored. `ChannelLink.link` declared `validators=[validate_channel_link]`, but Django only runs field validators from `full_clean()`, which `Model.save()` does not call and which nothing in this project called — so the validator was dead code outside the admin form, while the importer, the one path fed by third-party channel lists, writes through `update_or_create`. A `javascript:` or `data:text/html` URI therefore reached the page's `href` intact, where escaping is no defence because the URL itself is the payload, and it would execute in the site's own origin on click. Reproduced end to end before fixing. `ChannelLink.save()` now applies the validator to that single field, which cannot fail on an unrelated one and keeps `full_clean()`'s unique query out of every save; the importer catches the rejection, reports it and carries on rather than abandoning the run over one bad entry; and `link_button.html` renders no anchor at all for a scheme that is not allowed, which is the only layer that covers a row already in the table. The scheme is read through `urlparse`, matching what the browser does — it lower-cases the scheme and strips tabs and newlines — so `JavaScript:` and `java&#9;script:` are caught too. All 381 links in production were audited beforehand: every one is `acestream`, so nothing legitimate stops rendering.
- Pillow upgraded from 12.1.0 to 12.3.0. The old version is in range for `CVE-2026-25990` (out-of-bounds write) and `CVE-2026-42311` (integer overflow), both of which can lead to arbitrary code execution when a crafted PSD file is parsed, and for `CVE-2026-59203`, an infinite loop in the EPS parser. This project feeds Pillow image bytes downloaded from URLs found in scraped HTML, and Pillow selects its decoder by sniffing the content rather than trusting the extension, so a URL ending in `.webp` that serves a PSD reaches the vulnerable decoder.
- Django upgraded from 6.0.1 to 6.0.8, which is five security releases of accumulated fixes. Several apply directly to how this project is built rather than being theoretical: `CVE-2025-14550` is a denial of service in `ASGIRequest` via repeated headers and the site is served by uvicorn over ASGI; `CVE-2026-25674` concerns the file-based cache and file-system storage backends creating objects with unintended permissions, and both are in use; `CVE-2026-35193`, `CVE-2026-8404` and `CVE-2026-48587` are private-data exposure through `cache_page` and `Vary` handling, and every public view here is wrapped in `@cache_page`; `CVE-2026-15920` is cross-site scripting via `URLField` values rendered as links in the admin, which is where `ChannelLink.link` is edited. Staying on the 6.0 series rather than moving to 6.1 keeps this a security fix with no feature-release risk.

## [0.3.1] - 2026-08-11

A competition's crest strip overflowed by a single team, and the control offering to
reveal the overflow stayed on screen even when there was none. Both are layout questions
the server cannot answer, so the fix decides them where the page is rendered.

### Added
- `screenshot` Makefile target to capture a page headlessly, for reviewing the site without a browser extension. It tries Firefox first and falls back to Chrome, because a desktop Firefox that is already running hands the URL to the open instance and captures nothing while still exiting successfully. The result is checked rather than assumed, so the target fails when no image was produced instead of reporting one that is not there, and it warns when the URL did not answer 2xx, since a browser will happily photograph its own error page.

### Fixed
- The competition crest strip no longer overflows by a single team on a desktop viewport: the gap between crests goes from `gap-3` to `gap-2`, which fits all 20 La Liga crests on one row.
- The expand chevron beside that strip hides itself when the strip does not overflow, instead of offering to reveal nothing. Whether it overflows depends on the viewport width and the number of crests, which the server cannot know, so the button ships with the page and decides on render, on resize and once images have loaded.

## [0.3.0] - 2026-08-10

Events the scraper was quietly throwing away are now reported. Nothing about what gets
stored has changed: the point is knowing what does not.

### Added
- `remote-import-links` Makefile target to import a channel-link file into production. The file travels through the server's shared bind mount rather than `docker cp`, since `/tmp` inside the container is a tmpfs, which makes a copy into it report success while staying invisible to the process; it is removed when the run finishes.
- `newera.txt` and `elcano.txt` to `.gitignore`. `AGENTS.md` already said these external data files must never be committed, but nothing stopped it.

### Changed
- The scraper counts events whose broadcast time has not been announced ("PD") as `pending_time` instead of folding them into `skipped`, and names each one in the log. They are still not stored: an entry with no time has nowhere to sit in a listing ordered by time, and inventing one would put a false hour on the agenda. This was the only discarded row that raised no warning, which is how 44 of them a run went unnoticed — among them a Barcelona and a Real Madrid match. Running it against the source drops `skipped` to zero on every page, so every row being discarded was one of these rather than a parsing failure.
- `ScrapingStats.add()` folds a page's counters into the totals, replacing the counter-by-counter addition written out in two places, where a new counter could be added to one and forgotten in the other.

## [0.2.1] - 2026-08-10

Two silent faults in the logic that decides which channel a scraped link belongs to,
found by pinning its behaviour down with tests before touching it, and the rewrite those
tests then made safe.

### Added
- Characterization tests for `match_channels`, the logic deciding which channel a scraped link attaches to: 41 cases covering exact and parenthesised matches, the short-name guard, the DAZN variants, numeric suffixes, the token fallback and malformed input. It had no direct tests at all.

### Changed
- `match_channels` matches against the channel list in memory instead of querying per candidate: one query for a whole import run rather than three per entry, measured at 1236 queries and 638 ms down to 1 query and 11 ms for 200 names. Verified identical on all 87 production channel names and their variants — no case loses a match — beyond the accent fix noted below.

### Fixed
- Channel names in upper case with accented characters now match. SQLite only case-folds ASCII, so `iexact` never saw "ARAGÓN TV" as "Aragón TV"; matching in Python does. Twelve of the eighty-seven channels are affected, and playlists commonly shout their names, so those links were reported as belonging to no channel and dropped.
- A channel name that normalises to empty no longer matches every channel with a bracketed suffix — 34 of them on the production database. Reachable, since `fix_name` reduces a name consisting only of a mirror marker, `(*)` or `(**)`, to an empty string, after which the parenthesised-variant clause read it as a wildcard. Production data was checked and is unaffected: no link is attached to more than eight channels.

## [0.2.0] - 2026-08-10

A release dominated by a code review and the production work that came out of it: seven
confirmed bugs, two of them causing silent data loss, the transport security of a
publicly reachable admin, and a deploy that can no longer report success over a broken
site. The application code is now annotated and type-checked.

### Added
- Type annotations across the application code, checked by mypy with django-stubs through a new `make typecheck`, and ruff's ANN rules inside `make lint` so unannotated code cannot land. `mypy`, `django-stubs` and `types-requests` added to the requirements.
- `soccertime/rendering.py`, the single source of image markup for both the templates and the admin, exposed to templates as the `render_image_markup` filter. Models keep the image and its dimensions; the HTML lives outside them, so templates no longer need `|safe`. This finishes the decoupling the filter was introduced for.
- Test modules for `filters.py` and the template filters, which had none.
- `DJANGO_CACHE_LOCATION` to configure the file cache path.
- `redownload_images` management command (with `--dry-run`) to restore flag images whose file is missing from storage, re-fetching them from the URL each `Flag` keeps in its `name`.
- Shared `_image_download` module so `scrapit` and `redownload_images` use one guarded implementation of the image download.
- `EventQuerySet.chronological()` for the listing order (start time, then sport order, then competition name), now that the model default no longer carries it.
- `empty_state()` view helper and `soccertime/empty_state.html`, replacing the messages-based empty notice.
- `image_width` / `image_height` on `Flag` and `crest_width` / `crest_height` on `Team`, recorded by `save_image` and backfilled for existing rows, so rendering never opens an image file to measure it.
- Transport security settings driven from the environment through a new `env_flag()` helper: `DJANGO_BEHIND_TLS_PROXY`, `DJANGO_SECURE_COOKIES`, `DJANGO_SECURE_SSL_REDIRECT`, `DJANGO_SECURE_HSTS_SECONDS`, `DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS` and `DJANGO_SECURE_HSTS_PRELOAD`.
- `backup-remote-media` Makefile target, run by `deploy-production`, keeping the snapshot on the host rather than inside the volume it protects.
- `soccertime/backups.py`, applying generational retention to the snapshots — the last 3, one per day for 7 days, one per month for 12 months — because a plain count measures history in deploys rather than in time: six deploys in one afternoon evicted a five-month-old restore point. Database snapshots are now taken through SQLite's backup API and gzipped, so they are both consistent and a third of the size.
- `pull-remote-backups` Makefile target, since the database, the media and every snapshot otherwise live on the same machine.
- Crest reporting in `redownload_images`: broken references are listed even though a `Team` stores no source URL and therefore cannot be re-fetched automatically.
- `remote-smoke-test` and `wait-remote-healthy` Makefile targets, run at the end of `deploy-production`, so a deploy that leaves the site broken fails instead of reporting success. Pages are fetched from outside the server, because an unhealthy container is dropped from the proxy's routing table while still answering 200 on localhost.
- Makefile targets for production operations: `backup-remote-db` (run automatically by `deploy-production` before migrating), `list-remote-backups`, `restore-remote-db`, `remote-check`, `remote-clear-cache` and `remote-redownload-images`.
- `CLAUDE.md`, pointing at `AGENTS.md` and recording the verification rules learned from two production incidents.
- `duration` field (`DurationField`) to `Event` model allowing custom event durations (defaults to 2 hours if not specified).
- `validate_channel_link` validator to `ChannelLink.link` supporting IPTV and P2P protocols (`acestream`, `sop`, `rtmp`, `m3u8`, `intent`, `http`, `https`).
- Expanded test suite with 18 unit tests covering custom event durations across midnight, P2P link validation, manager forwarding, and template tags.
- Scraper support for team-specific pages in the `futbolenlatv` source to capture extra events (e.g. friendlies) not listed in the general agenda.
- Auto-discovery mechanism in `scrapit` command to automatically extract and persist team slugs from `<a>` tags during standard scraping.
- `futbolenlatv_slug` field to the `Team` model to store the identifier used on the source website.
- `local_slug` and `visitor_slug` fields to `MatchDetails` to decouple slug extraction from database persistence.
- `importm3u` management command to import acestream links from M3U playlist files (e.g. `mundial.m3u`), with the source name derived from the file name stem and an optional `--source` override.
- `*.m3u` pattern to `.gitignore`, since M3U playlists are external data sources that must not be committed.
- Rule in `GEMINI.md` to officially assign complex bug investigations and UI error diagnosis to the Opus 4.6 Architect subagent.
- Visual highlight (orange/gold left border) to `agenda_item.html` for matches involving favorite teams.
- `is_favorite_cached` property on `Team`, and `is_favorite_event` on `Event`, overridden by `Match`.
- Database prefetching for favorite relationships in `EventQuerySet.with_related()` to prevent N+1 queries.
- Rule regarding regression testing for bug fixes in `AGENTS.md`.
- Competition/Events title header to `agenda.html` to improve context visibility when filtering.
- Language and localization rules to `AGENTS.md`.
- Isolated `.geminiignore` and `.claudeignore` to prevent context duplication between LLM CLIs.

### Changed
- `LinkSchemeFilter` resolves the distinct link schemes with a single database query instead of reading every row into Python, and returns them in a stable order; they came from a set, so the admin dropdown could be ordered differently in each process.
- The admin attaches its generated relation columns once at registration instead of rewriting them on the shared `ModelAdmin` instance on every request, and reads `field.choices` rather than the private `field._choices`.
- `event_type` is applied by `Event.save()` from an `EVENT_TYPE` declared on each subclass, and the constant `is_favorite_event` default moved to `Event`, replacing three near-identical overrides apiece.
- Views share `get_base_context(with_teams=...)` instead of asking for the favourite teams and popping them back out, and their imports moved to module scope.
- The import commands roll a dry run back with `transaction.set_rollback(True)` instead of raising `TransactionManagementError` at themselves; `self.warnings` is created by the base command that consumes it.
- The empty-state strings are named constants wrapped in `gettext_lazy`. They still render in Spanish, as the site does.
- Docstrings, comments and management-command output are in English, per the project convention. The web interface stays in Spanish; only the code artifacts and the CLI changed, along with the stat keys in the link importer.
- The `env` template filter only reads allowlisted variables. It reaches every template, so `{{ "DJANGO_SECRET_KEY"|env }}` would otherwise render the secret into a page.
- `scrapit` upserts every event type through one `upsert_event`, replacing the same get / realign / dedupe algorithm copy-pasted three times.
- With caching disabled the cache backend is now explicitly `DummyCache`. Django's default is a per-process `LocMemCache`, which made the `cache.clear()` in the management commands appear to work while clearing only that process.
- `Event.Meta.ordering` reduced to `["date"]`. Ordering by competition and sport joined both tables and cast the timestamp on every query, including counts, lookups and admin lists; `Event` queries went from 2 joins to 0 and `Match` from 3 to 1.
- `ChannelLink.link` is unique again, restoring the constraint lost in migration `0029` and making the `update_or_create` upsert in `import_entries` safe. Existing duplicates are merged into the oldest row, which inherits its sources, channels and `verified` flag.
- Empty-state notices travel in the view context instead of the `messages` framework, which also removes one `.exists()` query per view. `AGENTS.md` updated accordingly.
- Refactored `EventManager` to `EventQuerySet.as_manager()` in `soccertime/models.py`.
- Removed redundant `event_ptr` from `unique_together` constraints on child MTI models (`Match`, `Race`, `SimpleEvent`).
- Refactored `Favorite.__str__` to safely handle unassigned or missing team/competition relations.
- Massive performance optimization (75% execution time reduction) in `scrapit` command by using `.set()` for Many-To-Many channel assignments, avoiding thousands of individual SQLite commit transactions caused by `clear()` and `add()` loops.
- `make test` and `make test-cov` now exclude integration tests (`-m "not integration"`) so the suite runs fast and offline; added `make test-integration` for the tests that scrape real sources.
- Extracted the shared link-import pipeline (name normalization, quality extraction, fuzzy channel matching, persistence and stats) from `addlinksource` into `BaseLinkImportCommand` (`_link_import_base.py`) for reuse by `importm3u`.
- Increased the mobile tab bar breakpoint trigger from `sm` (576px) to `md` (768px) to prevent layout breakages on tablets and landscape phones, offering a better mobile-like experience on medium screens.
- Decoupled `GEMINI.md` from `AGENTS.md` and added specific multi-agent workflow rules.

### Removed
- `channel_matchers.py`: 320 lines imported by nothing, advertised by Django as a command it could not run.
- `Sport.competitions_with_events`, `Sport.competitions_without_events` and `Competition.is_favorite`: superseded or byte-identical duplicates, used by nothing but the tests that kept them alive.
- `render_image`, `flag_image` and `crest_image` from the models, along with the duplicated fallback SVG. The markup moved to `soccertime/rendering.py`.
- `migrate_crests` management command. A one-off path migration from early 2026 whose "missing or empty file" branch cleared the crest reference of any team whose file was absent, turning a dangling reference the scraper repairs by itself into permanent loss: 1357 teams lost their crest that way.
- Legacy and redundant template files: `events.html`, `match_item.html`, `simple_event_item.html`, and `event_header.html`.

### Fixed
- The scraping dataclasses declared every field optional though `parse_iter` only yields complete events, and `Event.details` was typed `EventDetails` while the code passes `MatchDetails` and `RaceDetails`, which do not inherit from it; it is now a declared union narrowed by the existing `isinstance` dispatch.
- `team_events` sorted opponents with `opponent_dates.get(team.id)`, which would have raised `TypeError` inside `sorted` had the lookup ever missed.
- The link importer indexed `channel_link.link`, a nullable field, when reporting a duplicate.
- The channels page orders the links inside each card the same way the rest of the site does. It sorted only by the grouping keys, so the rows of a single card — which share all three — came back in whatever order the database chose, and the same play buttons appeared in one order there and another in the agenda. `CHANNEL_LINK_ORDERING` is now the single definition, used by the model and by the view.
- `upload-only` now extracts the uploaded archive. It left it packed, so a following `remote-restart` rebuilt the image from the previous version while reporting success.
- Deleting a `ChannelLinkSource` no longer destroys every source-less `ChannelLink`, including links created by hand in the admin. Only the links that belonged to the deleted source are considered.
- Detaching a link from the source side (`source.links.remove(...)`, as the admin form does) no longer raises `AttributeError`; the `m2m_changed` receiver honours `reverse` and `pk_set`.
- `/agenda/?events-date=<garbage>` returns the default agenda instead of HTTP 500.
- `EventQuerySet.favorites()` no longer duplicates an event when a team is listed in several `Favorite` rows.
- Scraping no longer aborts when a crest URL is missing or unreachable; failures are reported and skipped.
- `render_image` no longer opens each image file to measure it, cutting a 40-image page from 13.53 ms to 1.68 ms.
- Loading a row whose image file is missing no longer raises `FileNotFoundError`. Declaring `width_field` hooked Django's `update_dimension_fields` to `post_init`, which took `/competitions/` down with a 500 in production.
- The container health check is exempt from `SECURE_SSL_REDIRECT`. It reaches the app over plain HTTP, and a 301 made it fail, marking the container unhealthy and withdrawing it from the proxy, which returned 404 for every page.
- `BACKUP_SUFFIX` in the Makefile is an immediate assignment; as a recursive variable it re-ran `date` on every expansion and could name a different file than the one it created.
- Fixed `attempt to write a readonly database` in production management commands: remote SSH targets in the `Makefile` (`remote_deploy`, `upload-db`, `upload-requests-cache`, `upload-media`) hardcoded the local host UID (`DOCKER_UID`), which did not match the production container's `appuser` (UID 1000, owner of the data volumes). Introduced dedicated `REMOTE_DOCKER_UID`/`REMOTE_DOCKER_GID` variables (default 1000) for remote targets, decoupling them from the local `DOCKER_UID`.
- Fixed over-broad token fallback in the channel matcher (`BaseLinkImportCommand.match_channels`): short tokens ("5", "mx") were dropped, letting a generic token like "canal" associate a link (e.g. "CANAL 5 MX") to every unrelated "Canal *" channel. Short tokens are now required with word-boundary matching.
- Marked `test_dry_run_does_not_save` with the `integration` marker since it scrapes the real futbolenlatv source; the full non-integration suite no longer performs network requests.
- Fixed global N+1 query issue in `base.html` by adding `.select_related("flag")` to `get_favorite_competitions()` context processor.
- Fixed N+1 query issue in Django Admin's `EventModelAdmin` by prefetching channels for the `channels_names` column.
- Fixed severe N+1 query overhead in properties `is_favorite`, `has_events`, and `events_count` of `Competition` by refactoring them to use Python list comprehensions, enabling them to leverage the `prefetch_related` cache instead of hitting the database repeatedly.
- Fixed performance overhead in default `EventManager` by removing the implicit `with_related()` call, resolving massive `JOIN` drags on simple `.count()` and `.aggregate()` operations. Views now explicitly call `.with_related()`.
- Fixed performance bottleneck in `scrapit` command by introducing an in-memory local cache (`dict`) for `Team`, `Sport`, `Competition`, `Flag`, and `Channel` objects, drastically reducing `get_or_create` database operations during scraping loops.
- Fixed mobile layout for pagination overflowing the screen by wrapping elements in `agenda.html`.
- Fixed severe layout bug causing the `fixed-bottom` mobile navigation bar to overflow horizontally and detach vertically from the viewport by wrapping the `<table class="table">` in `agenda.html` with a `.table-responsive` container, preventing it from widening the body width.
- Fixed expandable teams bar not working on competition pages by moving the toggle script outside the favorites block in `base.html` and standardizing the UI component in `agenda.html`.
- `/healthz/` endpoint for Docker healthchecks, independent of the application cache.
- Intermittent 404 on `/soccertime/favorites/`: replaced per-site cache middleware (`UpdateCacheMiddleware`/`FetchFromCacheMiddleware`) with per-view `@cache_page` decorators. The per-site middleware was caching responses from the Docker healthcheck (which bypasses Traefik's `StripPrefix`), polluting the cache with entries keyed under inconsistent `SCRIPT_NAME` contexts. Per-view caching gives granular control and prevents the healthcheck from contaminating the cache.
- `Event.child_event` property to handle polymorphic event types (`Match`, `Race`, `SimpleEvent`) cleanly in templates.
- ARIA labels to all interactive elements and links for better accessibility.
- Flags to competitions in the favorites bar for visual consistency.
- F1 multi-session scraping: all sessions of the same Grand Prix weekend (Libres, Clasificación al Sprint, Sprint, Clasificación, Carrera) are now stored as independent `Race` records. Previously, all sessions shared the same race name and fell within the ±2-day deduplication window, causing `MultipleObjectsReturned` which deleted all but the most recent record, keeping only the Sunday race.
- Idempotency in `scrapit` command: `Race` and `SimpleEvent` deduplication now includes `details` (session type) as part of the lookup key, so only the datetime shifts within the same session type trigger an update.
- Removed hardcoded empty state alerts in favor of the global Django messages system.
- Deployment building unrelated images: `remote_deploy` and `remote-restart` now explicitly target the `soccertime-web` service.
- PermissionError during `collectstatic` in production: added a step to `chown` the static volume to the application user before running management commands.
- Horizontal scroll issue on Fire TV Silk: removed `text-nowrap` from table cells and reverted quick-access bars to show only crests to save horizontal space.
- PermissionError ("Operation not permitted") when downloading the database, requests cache, or media via `Makefile` by correctly setting file ownership on the remote host.
- `sqlite3.OperationalError` during `scrapit` in production: moved `requests_cache.install_cache()` out of module-level code into `_configure_cache()`, called lazily from `get_events()`. Added `os.makedirs(..., exist_ok=True)` to guarantee the cache directory exists before SQLite tries to open it. Also removed the spurious `.sqlite` extension from `REQUESTS_CACHE` in the Dockerfile (the library appends it automatically).

### Security
- Session and CSRF cookies are marked `Secure` in production, where the admin is publicly reachable and they previously travelled without the flag.
- HSTS enabled with a one-year lifetime, after confirming the public pages serve no `http://` resources. `includeSubDomains` and `preload` stay off deliberately, and their checks are silenced with that rationale so `check --deploy` stays a useful signal.
- `SECURE_SSL_REDIRECT` and `SECURE_PROXY_SSL_HEADER` enabled in production, so Django both recognises proxied HTTPS and redirects plain HTTP itself.

## [0.1.0] - 2026-03-08

### Added
- `DOCKER_UID` and `DOCKER_GID` variables with fallbacks (1000:1000) to `Makefile` for consistent user mapping across development and deployment.

### Fixed
- Permission issues in `upload-db`, `upload-requests-cache`, and `upload-media` targets by adding `chown` commands. This ensures that files uploaded to Docker volumes are owned by the application user instead of `root`.

### Security
- Explicitly set the `-u` flag in all `docker compose exec` commands within the `Makefile` (both local and remote) to strictly enforce the `appuser` (1000:1000) context.

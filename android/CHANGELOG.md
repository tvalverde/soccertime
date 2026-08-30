# Changelog — the Android applications

All notable changes to `es.mojon.soccertime` (phone) and `es.mojon.soccertime.tv` (Fire TV),
which live under `android/` and share the `:core` module.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and these applications adhere to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

They release on their own tags — `android-v*`, never a bare `v*`, because this repository also
holds the website and a bare version tag would be ambiguous about which of the two it names.
The website's own changelog is `../CHANGELOG.md`.

## [Unreleased]

### Added
- **The Compose test harness the applications never had.** `:app-mobile` and `:app-tv` gain a
  `src/test` on Robolectric + `compose-ui-test-junit4`, so what is drawn and what a gesture does
  are asserted on the JVM by `make android-test` — the CI step whose log used to read `NO-SOURCE`
  for both modules now runs real tests against the real resources. One earned lesson is written
  into the build files: `ui-test-manifest` must be `debugImplementation`, because Robolectric
  launches the harness activity from the merged debug manifest and a test-classpath manifest
  never merges into it. The screenshot flavour (pixel comparison) stays deliberately out.
- **Swiping horizontally moves between Favoritos and the Agenda on the phone.** The two sections
  are pages of one pager, synchronised with the bottom bar in both directions; a future section
  is one more page and one more tab. Tapping the Agenda tab while already on it still clears a
  crest-narrowed listing, and BACK still undoes the filter only while the agenda is the page on
  screen.
- **The agenda has a calendar.** The "Ayer y hoy" label — which looked pressable and answered to
  nothing — is now the control it appeared to be: it opens a date picker, and a chosen day
  narrows the listing to that day alone (one request, no yesterday), worn as a chip with a cross
  that returns to the two-day window. Choosing the day already shown asks the network for
  nothing.
- **Three text sizes on the phone.** An «Aa» control sits where the Editar button was and offers
  Pequeño, Mediano (the size every screen was designed at, and the default) and Grande. The
  choice multiplies the density's own `fontScale`, so every sp in the app moves together and the
  system's accessibility setting is composed with rather than fought, and it persists in a new
  settings store beside the favourites.

### Added (fifth batch, same day — mockups approved first)
- **Narrowed to a team or a competition, the agenda shows everything that is coming.** Tapping
  a crest used to show the same two-day window as the plain agenda; now it is the agenda
  without the daily stoppers: every event from today onward in one continuous listing, day
  headings kept for orientation, opening anchored on the event in progress, pages feeding
  themselves — no «MAÑANA» foot, no pull, because there is no frontier to cross. The chip
  beside the filter reads «Desde hoy», and the calendar takes a second meaning there: a chosen
  day moves where the listing *starts*, still endless onward. On television the narrowed
  listing feeds itself as the remote's focus nears the end, and the trailing row disappears.
- **The calendar dims the days that hold nothing, and refuses their press.** Powered by the
  API's new `/events/days/` — asked month by month as the reader flips, under the active
  narrowing, so a followed team's month lights only its match days. Deliberately fail-open:
  a month whose index never arrived stays fully pressable, because a nicety that failed must
  never lock a date away. Two beats keep the first open honest: the month is asked for when
  the chip is pressed, before the dialog exists, and the grid is rebuilt the moment an index
  arrives — the picker builds its month once and never re-asks `isSelectableDate`, so without
  the rebuild an answer landing a beat late dimmed nothing until the reader flipped months.

### Added (fourth batch, same day — mockups approved first)
- **The pull to tomorrow is visible while it is made, and fires on release.** The listing rides
  up with the finger at half a pixel per pixel while a ring in the foot fills with the pull;
  crossing the threshold arms it — ring closed and green over its tint, «Suelta para cargarlo»,
  a haptic tick — and the load fires when the finger leaves, never mid-drag. Dragging back down
  pays the stretch off before the list moves, so the gesture can always be walked out of, and
  letting go early springs everything back. A gesture spent stretching no longer flings the
  list on release.
- **«Ver más» is gone from the phone: the next page of a day asks for itself.** When the last
  ten rows of what is downloaded come into view the following page is requested, so in a
  normal scroll it has already arrived and there is no seam; only outrunning the network shows
  a quiet row with a small ring. While a failure stands the automatic ask pauses — parked at
  the end of a listing it would otherwise retry against the shared rate limit for as long as
  the reader stared at it — and the error banner's own Retry takes over. The television keeps
  its focusable «Ver más» row: a remote neither scrolls continuously nor stretches.
  One wording differs from the approved mockup, deliberately: the quiet row says «Cargando más
  eventos…» rather than «Cargando más de hoy…», because after pulling into tomorrow the pages
  being fetched are no longer today's and the label must not lie.

### Added (third batch, same day — mockups approved first)
- **The agenda continues into tomorrow by pulling past its end.** When a day is exhausted, the
  listing's foot names the next one («MAÑANA · LUNES 31 AGOSTO»); stretching upward past the
  end — or simply pressing the foot, so the feature exists before the gesture is found —
  appends that day under its own heading, and the foot moves on. Every extra day is one
  request, the active filters travel with it, and tomorrow is never reachable past an unshown
  tail of today: the foot is only drawn once the day's pages are done. With a calendar-chosen
  day the pull *moves* to the next day instead of growing — that view means "one day, only
  one" — and an empty chosen day still offers the way onward under its empty-state message.
  On television the same rule arrives as a focusable trailing row: «Ver más» while pages of
  the day remain — which also gives the remote its first way to page a day longer than a
  hundred events — and «Cargar MAÑANA …» once they are done.

### Added (second batch, same day — mockups approved first, as the new CLAUDE.md rule requires)
- **«Editar favoritos» opens on what is already followed.** A SIGUIENDO section, drawn from the
  local store alone — the names and crests are kept beside the ids, so it costs no request and
  renders before the network answers — sits above the catalogue, and each row's star unfollows
  it right there. Typing a search hides the section: the reader asked a different question.
  The list's keys carry the section name, because the same team appears in SIGUIENDO and in
  the catalogue below and a list keyed by the bare id crashes on the clash.
- **Favourites travel as a file now.** Exportar writes `soccertime-favoritos.json` through the
  system's save dialog; Importar reads it back through the system's open dialog and **merges by
  id — adds what is missing, never removes, never duplicates** (a file carrying the same id
  twice counts once, and something already followed keeps its current name). The result is
  announced: "Importados 4 favoritos: 2 nuevos, 2 ya seguidos". The envelope carries a
  `version` field, and the decoder requires it: every other field has a default, so without
  that requirement any JSON object would import as an empty success. Phone only — the
  televisions have no file manager to open the dialog with; that route is parked in TODO.

### Changed
- **`make android-install-mobile` refuses to run against more than one connected device without
  `ANDROID_SERIAL`, and `android-install-tv` pins the television it just connected.** Gradle's
  `installDebug` installs on every adb device attached at that moment — measured today, when it
  quietly put the phone app on both Fire TVs that had stayed connected over the network. The
  stray installs were removed the same minute.
- **The Editar button is gone from the favourites header.** It duplicated the (+) tile at the end
  of the followed strip — two controls to the same screen — and its spot now holds the text-size
  control. The (+) tile keeps its «Editar» caption and remains the way in.
- **Loading is unmissable now.** Both applications used to fill the first seconds with one muted
  13.5sp line — the same voice as an empty state, so a screen busy answering read exactly like a
  screen with nothing to say. The phone's listings share a `LoadingState` (a ring in the
  palette's loudest green, a display-face title, a body line) and the television draws the same
  claim by hand, `tv-material` shipping no progress indicator.

### Fixed
- **The favourites screen now fetches its whole three-day window instead of one page of it.**
  It asked for "today onwards" and read only the first hundred events — on a normal Saturday
  that page ends at teatime the same day, so everything followed tomorrow or the day after was
  quietly missing while the website, which filters server-side, showed it. The load now bounds
  the request to the window with `date_from`/`date_to` and walks the pages until the server
  says there are no more (capped at ten, a third of the shared thirty-a-minute budget). A page
  lost mid-walk fails the whole load rather than showing a window with a silent gap at its
  end, and what was on screen stays up, marked stale. Measured against production on a
  Sunday: 335 events in the window, of which the old single page carried at most 100 — and
  after the local three-hours-back trim, none of them later than the same evening.

### Added
- **Each release now says which website release it was built against.** These applications read
  the site's API and the two ship on separate tags, so nothing recorded the pairing — the
  question "which API does this APK need?" had no answer and never would have. The workflow asks
  `git describe` at build time, while the answer still exists, and prints it into the release
  notes.

  It does not gate anything, on purpose. An application-only version — a layout fix, a
  placeholder — needs no new website tag, and a check that fails on the honest cases is one
  people learn to work around. Recording is enough to make a mismatch visible: at the commit
  `android-v0.1.0` sits on, `git describe` answers **v0.8.0**, because the site was not tagged
  until later that day. A reader who knew the API was new would have seen the gap in the notes.

  The checkout had to grow with it. `actions/checkout` clones one commit and no tags by default,
  so `git describe` would have failed on the runner and nowhere else — the same shape as the
  signing password that fell back on null and never on the empty string GitHub actually sends.
  `fetch-depth: 0`, and a test that fails if it goes back.

## [0.1.0] - 2026-08-29

The first release. Both applications carry `versionName = "0.1.0"`, which the release workflow
checks against the tag before it will build anything.

### Added
- **Two native Android applications under `android/`**, reading the same public API the site
  serves: `es.mojon.soccertime` for a phone and `es.mojon.soccertime.tv` for the Fire TV
  Stick 4K, over one shared `:core` module holding everything that is not a screen. Different
  application ids, so both install on one device; the television registers under
  `LEANBACK_LAUNCHER`, which is the only category the Fire TV home screen lists.

  **`minSdk` is 25 because the Fire TV is Android 7.1, and that decides most of what follows.**
  `java.time` does not exist there and every instant this app handles is an ISO-8601 string
  with an offset, so core library desugaring carries `OffsetDateTime` down rather than a
  second date library. More seriously, `www.mojon.es` presents a chain that anchors at
  **ISRG Root X1** — today by way of Root YR cross-signed from it — and the trust store on
  that hardware is Amazon's, not Google's. There is no fallback to fail over to, because the
  site sends HSTS and redirects `http`, so a handshake that fails is a blank app rather than
  a degraded one. Both root generations are bundled through a `network_security_config.xml`
  declared in `:core`'s manifest, where neither application can ship having forgotten it, and
  the four certificates were checked to be inside the built APK rather than merely in the
  source tree.

  Times are rendered in the **device's** zone, deliberately unlike the site, which shows
  Madrid's to everybody. That is right for a page whose readers are all watching Spanish
  television and wrong for something carried: a phone in the Canaries shows 16:00 for the
  kick-off the site calls 17:00, and shows it under the day it falls on there — which for a
  late kick-off is the day before. Both the clock and the zone are injected, because a test
  that read either from the machine would pass in Madrid in August and nowhere else.

  Favourites are held on the device, since the API has no per-caller state, and the rule that
  decides what they cover is `EventQuerySet.for_selection` rather than `favorites()`: a team
  on either side of a match, or the event's competition for any event type including matches,
  with an empty selection covering nothing. One request fetches the window and the filter runs
  locally — one request per followed team would spend a rate limit that is thirty a minute per
  address and shared by every device in the house.

  Playing a link requires no particular player and names none: the URL is handed to the system
  exactly as the API returned it, and the system decides who answers. No installation check,
  no `<queries>` block, no chooser wrapper that would override a default the reader has set.
  When nothing answers, the app says so and offers to copy or share the link.

  The two faces the site uses are carried as files, one per weight. Android's downloadable
  fonts are served by Google Play services, and a Fire TV has none: there, a downloadable font
  is a silent fallback to the system sans-serif. Variable originals are no use either, because
  their axes need API 26 and this targets 25 — a variable file would render every weight at
  its default and flatten the hierarchy the design is built on.

  The agenda's view model is shaped by the rate limit rather than by the screen: typing is
  debounced and a query under two characters is treated as no query, a page holds the hundred
  the API allows, a manual refresh inside five seconds does nothing, returning to the screen
  reloads only what is over a minute old, and following a team re-draws the marks without
  asking again. When a load fails and the query has not moved, the last good answer stays on
  screen with a banner — an agenda a minute out of date is worth more than no agenda on a
  screen people open to find out what is on right now.

  The landing screen asks for nothing while nothing is followed, so a fresh install works
  before the device has ever been online, and following one more team narrows the window
  already on screen instead of fetching it again. What is followed is stored with its name and
  crest beside the id — deliberate denormalisation, because resolving five ids through the API
  would be five requests before the first frame, to draw a strip.

  The phone's screens follow the validated designs. One play button per event opens a sheet
  grouping the links by channel and then by quality, numbered inside each group — the website
  puts twenty play icons in a row and a phone has no room for that, and the numbering is what
  makes "the third one worked" something a person can repeat next week. When nothing on the
  device answers the scheme, the dialogue names no application and offers no download: it
  offers to copy the link or share it.

  The icons are the site's own Bootstrap paths rather than Compose's `material-icons-core`,
  which is frozen at 1.7.8 and would mean pinning one Compose artifact years behind the BOM
  managing every other. Countable strings are plurals, because Spanish says "1 resultado".

  The television draws the same events with the same view models and a different hand. Its
  links panel is master and detail rather than the phone's sheet — two presses of a remote
  reach any link instead of twenty — and favourites are chosen on the phone, because typing a
  team name with a D-pad is the worst thing a television asks of anyone and there is a phone
  app here that does it well. Focus is drawn rather than delegated: `tv-material`'s `Surface`
  carries its own scale and glow, and the design settled on a neon border and a halo.

  `test_android_materials.py` refuses either application importing the other's Material.
  Both are on the television's classpath — `tv-material` depends on `compose.material3`
  itself — and both export types of the same name, so an import an editor completes builds and
  ships, and is found by somebody in front of a television unable to reach a button.

  Tagging `android-v<version>` publishes both signed APKs as a GitHub release. The signing key
  exists for one reason — Android refuses to install a version signed with a different key, and
  uninstalling takes the favourites with it — so the workflow verifies the signature rather
  than assuming it: a signing config that finds no keystore is not an error in Gradle, it is
  simply absent, and `assembleRelease` then writes an unsigned APK and reports success.

  Four defects that only a remote in a hand could show, found by driving the Fire TV over ADB.
  Every focusable control carried both `focusable()` and `clickable()`, which are two focus
  targets: the outer one took the focus and the inner one handled OK, so the whole television
  app could be navigated and nothing could be activated. `:core` declared `@Composable`
  members without the Compose compiler plugin, so its getters compiled without the `Composer`
  parameter the applications called them with — it built, it linted, the tests never touched
  Compose, and it died on launch. The icon paths were transcribed by hand and one was wrong,
  drawing the agenda's calendar with a side missing; they are now generated from the upstream
  Bootstrap SVGs into vector drawables that `aapt` compiles. And a screen showing nothing for
  the seven seconds the events endpoint takes to answer is indistinguishable from a broken
  app, so both apps say they are loading.

  The television can follow things itself. The menu button on any event offers its two sides
  and its competition, each with its current state, and OK toggles one — the only interaction
  on that screen that needs no keyboard, because every name is already on the television and
  choosing between three is what a D-pad is good at. It answers on every row, including the
  ones with nothing to play, which are most of the agenda and exactly where a team worth
  following turns up.

  98 JVM unit tests plus the repository's own, run in CI by a new `android.yml` workflow. `ci.yml` is deliberately left
  unfiltered so gitleaks keeps reading pushes that touch only `android/` —
  `test_android_workflow.py` refuses a `paths` filter there, because adding one looks like a
  tidy-up and would quietly stop scanning the tree where keystore passwords live.

### Changed
- **The Android agenda spans yesterday and today, and opens on what is on rather than at the
  top.** Midnight is not a boundary anybody observes: at 00:20 the match that kicked off at
  23:00 is still running, and a listing that began at the stroke of the hour had nothing to
  show. Two days do not fit in one response — a hundred is the largest page the API serves —
  so it is two requests, and their order is the design. Today is asked for first because it is
  where the reader is and it alone positions the list; it renders while yesterday is still in
  flight. Yesterday follows, asked for `ordering=-date` so a busy day keeps the hours next to
  midnight instead of spending its hundred on the small hours, and is reversed back before
  being prepended. Losing it costs the tail of the window and leaves today standing; losing
  today does not go on to ask.

  Everything earlier is a scroll away, and moving between days, or a calendar, are deliberately
  still not here.

- **What the reader follows is now a way in, not a legend.** Pressing an entry in the
  favourites strip opens the agenda narrowed to that team or that competition, through the
  `team=` and `competition=` filters the API already served and nothing used. On the
  television BACK returns to Favourites and drops the filter in one press — the same press
  that arrived, rather than dropping the reader into the whole two-day agenda, a screen they
  never asked for. On the phone it is the Agenda tab with the filter on it, so the bottom bar
  stays and both BACK and the tab itself clear it. The chip carries the crest and the name
  rather than the kind, because "Competición" reads as a category and not as the competition
  that was pressed.

- **On the television, the fill says the state and the halo says the cursor.** Four separate
  faults were one fault: a control drawing "you are here" and "the cursor is here" with the
  same resource, so where the two met one swallowed the other. It is now a single rule in
  `TvFocus.kt` that the rail, the channel column, the link tiles, the followed avatars and the
  event rows all use — background and border belong to state, a halo and a tenth of extra size
  belong to focus, and nothing else uses either. The growth is drawn rather than laid out, so
  a moving cursor no longer shoves its neighbours aside.

### Fixed
- **The release build would have signed with a blank password, and only on CI.** The fourth
  signing secret is deliberately absent: a PKCS12 keystore has one password, so the config
  falls back to the store's. But a secret the repository does not hold still reaches the runner
  — as an environment variable set to the empty string — and `""` is not null, so the bare
  elvis behind that fallback never fired there. On a developer machine, where the variable is
  genuinely unset, the same expression worked. Blank counts as absent now.

  Nothing had caught it because `android-release.yml` has never run: this would have been its
  first tag, and it would have failed at the signature check the workflow already does. Local
  success and release failure from one expression is the shape this project keeps paying for —
  the flag rows whose file was gone, the health check that carried no `X-Forwarded-Proto`.
  `test_android_release.py` now reads the expression and rejects one that falls back only on
  null.

- **The Material rule was checked at the window and not at the door.** `test_android_materials.py`
  read imports, so nothing stopped `api(libs.compose.material3)` from sitting in `:core` — green,
  and waiting for the first import to make it matter. It now reads the build files too: each
  application must declare its own Material and not the other's, and `:core` neither. Coordinates
  are resolved through the version catalog rather than matched by alias, comments are dropped so
  a commented-out line cannot satisfy an assertion, and a coordinate written out as a string is
  read as well as one written as an alias — all three of which were shown to slip past a first
  draft of the check.

  Two claims in that file were false and are gone. `androidx.tv:tv-material:1.1.0` does **not**
  depend on `androidx.compose.material3` — its metadata brings `material-icons-core` and nothing
  else of Material — so the classpath is narrower than the file claimed and the compiler, today,
  would already refuse the wrong import. And `ImageVector` never moved between `ui-graphics` and
  `ui`; it has been in `ui` throughout. A file arguing that facts about artifacts go stale should
  not have carried two that had.

- **`Retry-After` was bounded below and not above, and the screens narrow it to an `Int`.** Both
  applications pick a plural with `retryAfterSeconds.toInt()`, so a header past `Int.MAX_VALUE`
  wraps: `4294967296` would choose the wording for zero while printing four billion seconds. The
  parse now takes a value only within nought to an hour, and drops anything else instead of
  clamping it — what these screens do with the number is print it, so one that cannot be a wait
  belongs in the sentence that names no number at all. An hour is far past anything either
  refuser sends; both count in windows of a minute.

  Nothing in front of this API can produce such a header, and that is the point: this is the one
  correction here that `:core` could carry a real Kotlin test for, since the application modules
  still have no test source set. Three in `SoccertimeApiTest`, two of which fail without the
  bound.

- **The television threw away the one number a rate-limited reader needs.** `describeTv` mapped
  every `RateLimited` to "inténtalo en unos segundos" while `ApiError` was already carrying the
  seconds read off the header, and the phone was already showing them. It says how long now, with
  the same plural the phone uses, and keeps the generic sentence for a refusal that arrives
  without the header.

  Worth doing because both refusals in front of this API do send `Retry-After`, which until now
  was only ever tested against a `MockWebServer`. Measured through the local replica — which
  carries production's middlewares by inheritance rather than in its own file, so read the
  composed config and not the override: the throttle inside lets thirty through in the minute and
  refuses the next with `Retry-After: 42` and a JSON body, and Traefik at the edge — reached on
  `/api/v1/docs/`, which is a plain `TemplateView` and so passes no throttle on the way — answers
  `Retry-After: 1` with an `X-Retry-In` of 965 ms and `Too Many Requests` as plain text, once its
  burst of thirty is spent. Both numbers are true and they mean opposite things: a bucket
  refilling once a second against the remainder of a fixed minute.
  Someone holding a remote decides whether to wait or keep pressing, and forty seconds is not
  "unos segundos".

- **A crest whose file was gone left a hole in the row, on both applications.** The API serves an
  image URL whether or not the file is behind it, deliberately and for a reason it already paid
  for: reading dimensions off the file is what returned 500 from `/competitions/` when 49 flag
  rows pointed at files that had disappeared, so `serializers.py` says in as many words that a
  404 from the web server beats a 500 from here. That leaves the client one obligation, and the
  client never took it. Coil draws *nothing* for a request that fails, so `AsyncImage` without an
  `error` painter left blank space in a row that had already reserved room for the crest — and
  without `fallback`, the same for a URL the API never sent, which only worked because the
  composable branched on `url == null` before ever asking Coil. Both are painters now, and the
  three states the reader can do nothing about are drawn the same.

  Neither slot is a compile error, neither is a crash, and neither is visible on a machine whose
  media directory is complete. Production reads clean today — all 229 flags and the team crests
  checked over HTTP, 302 of 302 answering 200, the missing ones long since repaired by
  `remote-redownload-images` — which is precisely why this needed writing down rather than
  waiting to be noticed again.

  The fix had to be written twice or written once. `Crest` and `TvCrest` were byte-identical
  bodies in the two applications, so there is now one `Crest` in `:core`, beside the fonts and
  the icons that live there for the same reason. That cost `:core` an explicit
  `foundation-layout`: `Modifier.size` is in that artifact and not in `foundation`, which exports
  it on the runtime classpath but not the compile one — the applications never noticed because
  their Material brings it along, and `:core` carries no Material by design.

  `test_android_images.py` holds both halves: every `AsyncImage` must declare `error` and
  `fallback`, and only `:core` may import `coil3.compose`, so the copy that drifts cannot come
  back. The application modules still have no test source set, so a Python meta-test reading the
  Kotlin as text is what stands in for one — the same technique already guarding the two
  Materials.

- **The phone's bottom bar was laid out but invisible, which left the Agenda unreachable.** Its
  row said `fillMaxSize(fraction = 0f)` — zero per cent of *both* dimensions — and the `height`
  beside it only put one of them back. Sixty-six points tall and nothing wide. It is
  `fillMaxWidth` now, and the two tabs are on screen where they always claimed to be.

- **The hour on every phone card wrapped to two lines, and the LIVE badge became a green disc.**
  One measurement caused both: the column was fixed at 48 dp and `21:30` needs about 49, so the
  time broke, and the badge — squeezed into a nearly square box carrying a 50% corner radius —
  came out round. The column is 62 dp, which is what its two occupants ask for at their own type
  sizes with slack, and the time additionally refuses to wrap at all. Fixed rather than
  content-sized on purpose: a column that resized per row would zigzag by whether a row carried a
  badge, and an agenda is read by running down the left edge.

  Worth recording how this was diagnosed wrong first. The initial explanation was that the phone
  was narrower than the mock-up with a larger font; measuring it said the opposite — 426 dp at a
  font scale of 1.0, *wider* than the 390 dp drawn. The device had been blamed for what was a
  constant in our own source.

- **The bottom bar's icons sat flush against its top edge with the bottom half of the bar empty.**
  Each tab's box wrapped its content — 37 points of icon, gap and label — so the row placed it
  with its default alignment, which is top; the selected-tab indicator landed on the first row of
  pixels and 42 points below the label were painted and empty. `fillMaxHeight` gives the box the
  bar's full height so an alignment has something to align within, and the group rests on the
  floor with 3 points under it.

  Bottom, not centre, and the arithmetic is the reason. The bar paints edge to edge and holds the
  gesture strip — 24 points, measured on the device — below its own height, so for `h` points of
  bar the group's centre would be `h / 2` while the painted centre is `h / 2 + 12`. Centring
  leaves it high *at every height*, which is why the first instinct, making the bar taller, would
  have widened the gap rather than closed it. Measured after the change: 26 points above the
  group, 27 below, its centre 0.5 points from the painted one.

  These three are presentation-only and the app modules carry no test harness — all 131 tests
  live in `:core`, which holds the logic. They were verified by measuring the rendered layout on
  the device with `uiautomator dump` against the window insets `dumpsys window displays` reports,
  which is repeatable and is what caught the top-alignment that reading the source had missed.

- **The television's link panel closed itself to open a link, on top of a footer telling you to
  try the next one.** It stays open now, marks the one that was launched and keeps its channel
  selected, so a stream that does not start costs one press instead of finding the row again.
  It also puts the "nothing on this box opens that" notice *over* the links rather than
  instead of them, so BACK from it lands where the next attempt is made.

- **The agenda opens on what has just started, not on the oldest thing still running.** It took
  the first event that had not finished, which at half past six in the evening is a race that
  began at five — an hour and a half above the reader, with everything they might want below the
  fold. It is the last event whose hour has come: `start <= now`, so one starting exactly on the
  hour is the one you land on, with what is still to come reading downwards from it. When
  nothing has started, which is the favourites screen most of the time, it opens at the top.

  Favourites had its own version. The television opened it at the top and the phone, which asked
  for no anchor at all, fell through to a fallback and **scrolled to the last event on the
  list**. Both carry the same anchor now, taken from the events actually drawn rather than from
  everything fetched, so it can never name a row the window has filtered out.

- **A listing left behind no longer lingers on screen.** The television keeps this view model
  while the agenda is off screen, so returning through the rail painted the chip and the rows of
  the followed team just left, under a screen that no longer said why. The rows go when the
  filter does — guarded on the filter really changing, since both apps re-send it every time the
  screen re-enters composition and blanking a good screen on the way back to a tab would be a
  worse fault than the one being fixed.

- **A favourites file that failed to be read once was never read again.** `Flow.catch` completes
  the flow after emitting, so a single `IOException` from DataStore ended that collector for the
  life of the process: the screen kept whatever it held and stopped reacting to every change
  after it. It retries instead, backing off to half a minute, so a busy disk costs one empty
  reading rather than a session.

- **A sweep for everything else of the same shape.** Four bugs in a row had one cause —
  shared state written by the wrong thing, at the wrong time, or twice — so the rest were
  looked for by reading rather than waited for. Found and fixed:

  - **A followed team could be stored as a competition, permanently.** The star on a row
    decided which list to write to by reading the tab, and switching tabs changes the tab at
    once while leaving the old rows on screen for as long as the next request takes — for good
    if it fails. A row now says what it is. Anything already miswritten can be un-followed and
    followed again.
  - **Two presses of "load more" crashed the app.** The page number only advanced when a page
    arrived, so the second press fetched the same page again and appended it twice; a list
    keyed by event id does not survive one id appearing twice. The number is taken when the
    press happens and put back only if the page never comes.
  - **A page of a listing being replaced could join the one replacing it.** Narrowing to a
    followed team and asking for another page before it arrived appended the plain agenda's
    next hundred to the team's. No page is fetched while the list beneath it is being replaced.
  - **Retry did nothing.** On the agenda, after the first load of all had failed — the guard
    that avoids a redundant refresh read a field only ever written on success. On managing
    favourites, always: it re-sent the search text, and a `StateFlow` given what it already
    holds emits nothing.
  - **A failed narrowing could be undone by following something.** Re-marking rows redraws
    from what is already in hand without asking the server, and a failure cleared the days
    while leaving the events behind them — so the whole plain agenda came back under the
    followed team's chip, error banner and all.
  - **The window stopped following the day.** It was fixed when the screen was built, which on
    a television left composed for days meant fetching the window it was born with. It is
    asked for per load now, and coming back to the app is tied to the lifecycle rather than to
    entering composition, so waking the television actually asks again.
  - Smaller: the favourites screen could run two loads at once and let the older win; a
    `runCatching` around a suspending scroll swallowed cancellation, the very mistake that
    started this; the television's clock was read once and then told the time it was drawn at.

- **One followed thing's events appearing inside another's.** Leaving FC Barcelona for MotoGP
  gave a screen headed MotoGP, counting MotoGP's two events, with a Barcelona match sitting
  above them under AYER. Re-entering the agenda asks it to refresh, and a refresh reloaded
  whatever was *last loaded* rather than what is on screen — in a coroutine of its own,
  outside the single flight the query pipeline gives — so the window being left was fetched
  alongside the one being asked for and its yesterday prepended onto it. A refresh is a bump
  of the same pipeline now, which both picks up the current filter and cancels whatever is in
  the air. Every load also carries which load it is, and one that has been superseded stays
  quiet however late it answers.

- **A filtered agenda that reloaded itself back to everything.** Pressing a followed team
  narrowed the listing and then, seconds later, quietly replaced it with the whole two-day
  window again. `collectLatest` does cancel the load it replaces, but `safeCall` caught
  `CancellationException` along with everything else — and a cancellation that is caught is
  not a cancellation. The abandoned load carried on, published its own answer, and whichever
  finished last won. It is rethrown now, first, before the catch-all, and the view model
  additionally refuses to publish an answer whose work has been abandoned: a request can
  return in the instant between being cancelled and the next suspension point, and writing
  state is not one.

- **A screen that could only be left once.** Marking everything behind an open panel
  unfocusable looked like the tidy way to keep the cursor out of the rows under the scrim. It
  is inherited by every focus target below it, the list's own group included, and once that
  group had been switched off and on again a focus search could no longer enter it: closing
  the panel put the cursor back on its row, LEFT still reached the rail, and RIGHT then found
  nothing at all — a screen that looked alive, since the rail kept answering, with an agenda
  that could not be reached. Each panel already traps the cursor inside itself, which is what
  that flag was for, so it is gone.

- **Two ways the remote could get stuck, both found by using one.** LEFT from the third link
  of a channel jumped back to the channel instead of stepping to the second: the redirect that
  belongs to the column's edge was written where every tile below it inherited it, so each one
  carried an instruction meant for the boundary. And closing the panel left the cursor nowhere
  at all — the node holding it is destroyed with the panel, the rail still answered because it
  sits outside the list, and the screen therefore looked alive while the events could not be
  reached. The list remembers which row it was on and asks for it back.

- **The cursor disappeared on the navigation rail.** `selected` was resolved before `focused`
  in the same `when`, so arriving at the icon of the screen you were already on changed
  nothing at all. The icon under the cursor also stayed muted, which was the other half of it.

- **The remote could get into the channel column and not back out.** The two columns were
  siblings with no focus rules, so the return trip was left to geometry — and moving onto a
  channel selects it, which rebuilds the whole right-hand column underneath the search that
  was about to look through it. LEFT and RIGHT are named explicitly now. The channel being
  read and the channel under the cursor were also drawn identically, by an `if (selected ||
  focused)`, which mattered precisely when the cursor had moved to the links.

- **UP from the first event jumped diagonally onto the rail.** Nothing sits above the top row,
  so the focus search settled for the nearest thing in any direction, which was a menu up and
  to the left. The list is a focus enclosure now: UP at the top, DOWN at the bottom and RIGHT
  anywhere are cancelled, and LEFT is the only way out — which is what the rail was always
  documented to be reached by.

- **The remote's play key did nothing.** A hand holding a remote at a listing of things to
  watch reaches for it; on a focused row it now opens the channels, as OK does. Both the
  dedicated play and the play/pause toggle, because the hardware is not consistent. Each
  television screen also carries a line of hints, since ☰ has always followed a team and
  nothing ever said so, and a D-pad has no hover to discover it with.

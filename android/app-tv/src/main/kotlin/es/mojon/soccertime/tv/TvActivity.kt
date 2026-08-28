package es.mojon.soccertime.tv

import android.app.Application
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.runtime.Composable
import androidx.lifecycle.repeatOnLifecycle
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.rememberCoroutineScope
import kotlinx.coroutines.launch
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.focusProperties
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.tv.material3.MaterialTheme
import coil3.ImageLoader
import coil3.PlatformContext
import coil3.SingletonImageLoader
import coil3.network.okhttp.OkHttpNetworkFetcherFactory
import coil3.request.crossfade
import es.mojon.soccertime.core.AppGraph
import es.mojon.soccertime.core.data.Following
import es.mojon.soccertime.core.playback.PlayResult
import es.mojon.soccertime.core.model.LinkDto
import es.mojon.soccertime.core.ui.AgendaFilter
import es.mojon.soccertime.core.ui.AgendaIntent
import es.mojon.soccertime.core.ui.AgendaViewModel
import es.mojon.soccertime.core.ui.EventLinks
import es.mojon.soccertime.core.ui.FavoritesIntent
import es.mojon.soccertime.core.ui.FavoritesViewModel
import es.mojon.soccertime.core.ui.Followable
import es.mojon.soccertime.core.ui.FollowableKind
import es.mojon.soccertime.tv.ui.TvAgendaScreen
import es.mojon.soccertime.tv.ui.TvDestination
import es.mojon.soccertime.tv.ui.TvFavoritesScreen
import es.mojon.soccertime.tv.ui.TvFollowPanel
import es.mojon.soccertime.tv.ui.TvLinksPanel
import es.mojon.soccertime.tv.ui.TvNoHandler
import es.mojon.soccertime.tv.ui.TvRail
import es.mojon.soccertime.tv.ui.theme.OverscanHorizontal
import es.mojon.soccertime.tv.ui.theme.OverscanVertical
import es.mojon.soccertime.tv.ui.theme.SoccertimeTvTheme

/** Holds the one graph, and points Coil at the client that carries the bundled trust anchors. */
class SoccertimeTvApplication : Application(), SingletonImageLoader.Factory {

    val graph: AppGraph by lazy { AppGraph.from(this) }

    override fun newImageLoader(context: PlatformContext): ImageLoader =
        ImageLoader.Builder(context)
            .components { add(OkHttpNetworkFetcherFactory(callFactory = { graph.client })) }
            .crossfade(true)
            .build()
}

class TvActivity : ComponentActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val graph = (application as SoccertimeTvApplication).graph
        setContent { SoccertimeTvTheme { SoccertimeTv(TvModels(graph, this)) } }
    }
}

/**
 * The whole television app is two screens and one panel, so there is no navigation graph: a
 * destination and a nullable panel say everything, and BACK reads better as "close what is
 * open, then leave" written in one place than as a back stack to reason about.
 */
@Composable
private fun SoccertimeTv(models: TvModels) {
    // Null until the store has answered, and the answer decides where the app opens: a
    // television whose reader has followed nothing would otherwise land on a screen that
    // invites a choice it cannot make here, with the agenda one unexplained press away.
    val following by models.following.collectAsStateWithLifecycle(null)
    var destination: TvDestination? by remember { mutableStateOf(null) }
    var showing: EventLinks? by remember { mutableStateOf(null) }
    // Which link of the open panel was launched. The panel no longer closes to launch one, so
    // it has to be able to say which it was — and the reader can try the next without
    // finding their way back to the row.
    var opened: LinkDto? by remember { mutableStateOf(null) }
    var unopenable: PlayResult.NoHandler? by remember { mutableStateOf(null) }
    var choosing: Pair<String, List<Followable>>? by remember { mutableStateOf(null) }
    // Chosen on the favourites screen and applied on the agenda, which is a different view
    // model that does not exist until the destination changes.
    var narrowing: AgendaFilter? by remember { mutableStateOf(null) }
    val scope = rememberCoroutineScope()

    LaunchedEffect(following) {
        val known = following ?: return@LaunchedEffect
        if (destination == null) {
            destination = if (known.isEmpty) TvDestination.Agenda else TvDestination.Favorites
        }
    }

    val opensOn = destination ?: return

    val covered = showing != null || choosing != null || unopenable != null

    Box(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background)) {
        Row(
            Modifier
                .fillMaxSize()
                .padding(horizontal = OverscanHorizontal, vertical = OverscanVertical),
            horizontalArrangement = Arrangement.spacedBy(26.dp),
        ) {
            TvRail(selected = opensOn, onSelect = { destination = it })

            when (opensOn) {
                TvDestination.Favorites -> {
                    val favorites = viewModel<FavoritesViewModel>(factory = models.favorites)
                    val state by favorites.uiState.collectAsStateWithLifecycle()
                    OnResumed { favorites.onIntent(FavoritesIntent.Resumed) }

                    TvFavoritesScreen(
                        state = state,
                        following = following ?: Following(),
                        clockLabel = rememberClock(models),
                        covered = covered,
                        onOpen = { row ->
                            opened = null
                            showing = favorites.linksFor(row.id)
                        },
                        onFollow = { row ->
                            choosing = row.label() to favorites.followablesFor(row.id)
                        },
                        onNarrow = {
                            narrowing = it
                            destination = TvDestination.Agenda
                        },
                        modifier = Modifier.weight(1f),
                    )
                }
                TvDestination.Agenda -> {
                    val agenda = viewModel<AgendaViewModel>(factory = models.agenda)
                    val state by agenda.uiState.collectAsStateWithLifecycle()
                    OnResumed { agenda.onIntent(AgendaIntent.Resumed) }
                    LaunchedEffect(narrowing) { agenda.onIntent(AgendaIntent.Narrow(narrowing)) }

                    TvAgendaScreen(
                        state = state,
                        covered = covered,
                        onOpen = { row ->
                            opened = null
                            showing = agenda.linksFor(row.id)
                        },
                        onFollow = { row -> choosing = row.label() to agenda.followablesFor(row.id) },
                        modifier = Modifier.weight(1f),
                    )
                }
            }
        }

        showing?.let { links ->
            TvLinksPanel(
                links = links,
                opened = opened,
                onOpen = { link ->
                    // Deliberately still open. A link that does not start is the ordinary
                    // case here — the panel's own footer has always said "try the next one"
                    // — and closing to launch one meant that advice was given on a screen
                    // that no longer existed. It also puts the failure dialog on top of the
                    // links rather than instead of them, so BACK lands where the next
                    // attempt is made.
                    opened = link
                    when (val result = models.playback.open(link)) {
                        is PlayResult.NoHandler -> unopenable = result
                        else -> Unit
                    }
                },
            )
        }

        choosing?.let { (title, candidates) ->
            TvFollowPanel(
                title = title,
                candidates = candidates,
                following = following?.selection ?: es.mojon.soccertime.core.data.Favorites.NONE,
                onToggle = { candidate, follow ->
                    scope.launch {
                        when (candidate.kind) {
                            FollowableKind.Teams -> models.favoritesStore.setTeam(candidate.item, follow)
                            FollowableKind.Competitions ->
                                models.favoritesStore.setCompetition(candidate.item, follow)
                        }
                    }
                },
            )
        }

        unopenable?.let { TvNoHandler(scheme = it.scheme, link = it.link) }
    }

    // BACK closes whatever is open before it leaves the app, which is the one thing a remote's
    // single back button has to get right.
    BackHandler(enabled = unopenable != null) { unopenable = null }
    BackHandler(enabled = unopenable == null && choosing != null) { choosing = null }
    BackHandler(enabled = unopenable == null && choosing == null && showing != null) {
        showing = null
        opened = null
    }
    // One press in from a followed team, one press back out. Clearing the filter without
    // leaving would answer a press nobody made by replacing three events with a hundred and
    // sixty-eight, on a screen the reader never asked for.
    BackHandler(enabled = showing == null && unopenable == null && choosing == null && opensOn != TvDestination.Favorites) {
        narrowing = null
        destination = TvDestination.Favorites
    }
}

/** What the panel calls the event it was opened from. */
private fun es.mojon.soccertime.core.ui.EventUi.label(): String =
    title ?: listOfNotNull(home?.name, away?.name).joinToString(" — ")

/**
 * Ask again every time the screen actually comes back.
 *
 * `LaunchedEffect(Unit)` fires when a branch enters composition, which is not the same thing:
 * a television is switched off with the composition intact and woken days later, and the
 * screen it comes back to had never been told to look again. `repeatOnLifecycle` runs this
 * each time the lifecycle reaches RESUMED, which is what "came back" means.
 */
@Composable
private fun OnResumed(ask: () -> Unit) {
    val lifecycle = androidx.lifecycle.compose.LocalLifecycleOwner.current.lifecycle
    LaunchedEffect(lifecycle) {
        lifecycle.repeatOnLifecycle(androidx.lifecycle.Lifecycle.State.RESUMED) { ask() }
    }
}

/**
 * The clock in the corner, ticking.
 *
 * Read once during composition it was the time the screen was drawn, which on a television
 * nobody has touched since lunchtime is a lie told confidently. It is a state that wakes each
 * minute instead — and only while this screen is composed, so it costs nothing when it is not.
 */
@Composable
private fun rememberClock(models: TvModels): String {
    var label by remember { mutableStateOf(models.now()) }
    LaunchedEffect(Unit) {
        while (true) {
            kotlinx.coroutines.delay(CLOCK_TICK_MILLIS)
            label = models.now()
        }
    }
    return label
}

private const val CLOCK_TICK_MILLIS = 30_000L

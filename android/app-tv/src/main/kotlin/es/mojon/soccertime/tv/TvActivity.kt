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
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
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
import es.mojon.soccertime.core.ui.AgendaIntent
import es.mojon.soccertime.core.ui.AgendaViewModel
import es.mojon.soccertime.core.ui.EventLinks
import es.mojon.soccertime.core.ui.FavoritesIntent
import es.mojon.soccertime.core.ui.FavoritesViewModel
import es.mojon.soccertime.tv.ui.TvAgendaScreen
import es.mojon.soccertime.tv.ui.TvDestination
import es.mojon.soccertime.tv.ui.TvFavoritesScreen
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
    var unopenable: PlayResult.NoHandler? by remember { mutableStateOf(null) }

    LaunchedEffect(following) {
        val known = following ?: return@LaunchedEffect
        if (destination == null) {
            destination = if (known.isEmpty) TvDestination.Agenda else TvDestination.Favorites
        }
    }

    val opensOn = destination ?: return

    Box(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background)) {
        Row(
            Modifier
                .fillMaxSize()
                .padding(horizontal = OverscanHorizontal, vertical = OverscanVertical)
,
            horizontalArrangement = Arrangement.spacedBy(26.dp),
        ) {
            TvRail(selected = opensOn, onSelect = { destination = it })

            when (opensOn) {
                TvDestination.Favorites -> {
                    val favorites = viewModel<FavoritesViewModel>(factory = models.favorites)
                    val state by favorites.uiState.collectAsStateWithLifecycle()
                    LaunchedEffect(Unit) { favorites.onIntent(FavoritesIntent.Resumed) }

                    TvFavoritesScreen(
                        state = state,
                        following = following ?: Following(),
                        clockLabel = models.now(),
                        onOpen = { showing = favorites.linksFor(it.id) },
                        modifier = Modifier.weight(1f),
                    )
                }
                TvDestination.Agenda -> {
                    val agenda = viewModel<AgendaViewModel>(factory = models.agenda)
                    val state by agenda.uiState.collectAsStateWithLifecycle()
                    LaunchedEffect(Unit) { agenda.onIntent(AgendaIntent.Resumed) }

                    TvAgendaScreen(
                        state = state,
                        onOpen = { showing = agenda.linksFor(it.id) },
                        modifier = Modifier.weight(1f),
                    )
                }
            }
        }

        showing?.let { links ->
            TvLinksPanel(
                links = links,
                onOpen = { link ->
                    showing = null
                    when (val result = models.playback.open(link)) {
                        is PlayResult.NoHandler -> unopenable = result
                        else -> Unit
                    }
                },
            )
        }

        unopenable?.let { TvNoHandler(scheme = it.scheme, link = it.link) }
    }

    // BACK closes whatever is open before it leaves the app, which is the one thing a remote's
    // single back button has to get right.
    BackHandler(enabled = unopenable != null) { unopenable = null }
    BackHandler(enabled = unopenable == null && showing != null) { showing = null }
    BackHandler(enabled = showing == null && unopenable == null && opensOn != TvDestination.Favorites) {
        destination = TvDestination.Favorites
    }
}

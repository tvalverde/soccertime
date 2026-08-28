package es.mojon.soccertime.mobile

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.consumeWindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import es.mojon.soccertime.core.playback.LinkSharing
import es.mojon.soccertime.core.playback.PlayResult
import es.mojon.soccertime.core.ui.AgendaIntent
import es.mojon.soccertime.core.ui.EventLinks
import es.mojon.soccertime.core.ui.FavoritesIntent
import es.mojon.soccertime.core.ui.ManageIntent
import es.mojon.soccertime.core.ui.Palette
import es.mojon.soccertime.core.ui.SoccertimeIcons
import es.mojon.soccertime.mobile.ui.AgendaScreen
import es.mojon.soccertime.mobile.ui.FavoritesScreen
import es.mojon.soccertime.mobile.ui.LinksSheet
import es.mojon.soccertime.mobile.ui.ManageFavoritesScreen
import es.mojon.soccertime.mobile.ui.NoHandlerDialog
import es.mojon.soccertime.mobile.ui.theme.SoccertimeTheme
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val graph = (application as SoccertimeApplication).graph
        setContent { SoccertimeTheme { Soccertime(Models(graph, this)) } }
    }
}

private object Routes {
    const val FAVORITES = "favorites"
    const val AGENDA = "agenda"
    const val MANAGE = "manage"
}

@Composable
private fun Soccertime(models: Models) {
    val navController = rememberNavController()
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val snackbars = remember { SnackbarHostState() }

    var showing: EventLinks? by remember { mutableStateOf(null) }
    var unopenable: PlayResult.NoHandler? by remember { mutableStateOf(null) }

    val copied = stringResource(R.string.link_copied)

    Scaffold(
        containerColor = MaterialTheme.colorScheme.background,
        bottomBar = { BottomBar(navController) },
        snackbarHost = { SnackbarHost(snackbars) },
    ) { padding ->
        NavHost(
            navController = navController,
            startDestination = Routes.FAVORITES,
            modifier = Modifier.padding(padding).consumeWindowInsets(padding),
        ) {
            composable(Routes.FAVORITES) {
                val favorites = viewModel<es.mojon.soccertime.core.ui.FavoritesViewModel>(factory = models.favorites)
                val state by favorites.uiState.collectAsStateWithLifecycle()
                val following by models.following.collectAsStateWithLifecycle(
                    initialValue = es.mojon.soccertime.core.data.Following(),
                )
                LaunchedEffect(Unit) { favorites.onIntent(FavoritesIntent.Resumed) }

                FavoritesScreen(
                    state = state,
                    following = following,
                    onIntent = favorites::onIntent,
                    onEdit = { navController.navigate(Routes.MANAGE) },
                    onBrowseAgenda = { navController.navigate(Routes.AGENDA) },
                    onOpen = { showing = favorites.linksFor(it.id) },
                )
            }

            composable(Routes.AGENDA) {
                val agenda = viewModel<es.mojon.soccertime.core.ui.AgendaViewModel>(factory = models.agenda)
                val state by agenda.uiState.collectAsStateWithLifecycle()
                LaunchedEffect(Unit) { agenda.onIntent(AgendaIntent.Resumed) }

                AgendaScreen(
                    state = state,
                    onIntent = agenda::onIntent,
                    onOpen = { showing = agenda.linksFor(it.id) },
                )
            }

            composable(Routes.MANAGE) {
                val manage = viewModel<es.mojon.soccertime.core.ui.ManageFavoritesViewModel>(factory = models.manage)
                val state by manage.uiState.collectAsStateWithLifecycle()

                ManageFavoritesScreen(
                    state = state,
                    onIntent = manage::onIntent,
                    onBack = { navController.popBackStack() },
                )
            }
        }
    }

    showing?.let { links ->
        LinksSheet(
            links = links,
            onDismiss = { showing = null },
            onOpen = { link ->
                showing = null
                when (val result = models.playback.open(link)) {
                    is PlayResult.NoHandler -> unopenable = result
                    else -> Unit
                }
            },
        )
    }

    unopenable?.let { blocked ->
        NoHandlerDialog(
            scheme = blocked.scheme,
            link = blocked.link,
            onCopy = {
                LinkSharing.copy(context, blocked.link)
                unopenable = null
                scope.launch { snackbars.showSnackbar(copied) }
            },
            onShare = {
                LinkSharing.share(context, blocked.link)
                unopenable = null
            },
            onDismiss = { unopenable = null },
        )
    }
}

@Composable
private fun BottomBar(navController: NavHostController) {
    val entry by navController.currentBackStackEntryAsState()
    val route = entry?.destination?.route ?: Routes.FAVORITES
    if (route == Routes.MANAGE) return

    Row(
        Modifier
            .fillMaxSize(fraction = 0f)
            .background(Color(Palette.HEADER))
            .windowInsetsPadding(WindowInsets.navigationBars)
            .height(66.dp),
    ) {
        BottomItem(
            label = stringResource(R.string.tab_favorites),
            icon = SoccertimeIcons.Star,
            selected = route == Routes.FAVORITES,
            modifier = Modifier.weight(1f),
        ) { navController.navigateTop(Routes.FAVORITES) }

        BottomItem(
            label = stringResource(R.string.tab_agenda),
            icon = SoccertimeIcons.Calendar,
            selected = route == Routes.AGENDA,
            modifier = Modifier.weight(1f),
        ) { navController.navigateTop(Routes.AGENDA) }
    }
}

@Composable
private fun BottomItem(
    label: String,
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    selected: Boolean,
    modifier: Modifier = Modifier,
    onClick: () -> Unit,
) {
    val tint = if (selected) MaterialTheme.colorScheme.primary else Color(Palette.ON_BACKGROUND_MUTED)
    Box(modifier.clickable(onClick = onClick), contentAlignment = Alignment.Center) {
        if (selected) {
            Box(
                Modifier
                    .align(Alignment.TopCenter)
                    .width(30.dp)
                    .height(3.dp)
                    .clip(RoundedCornerShape(bottomStart = 3.dp, bottomEnd = 3.dp))
                    .background(MaterialTheme.colorScheme.primary),
            )
        }
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(5.dp),
        ) {
            Icon(icon, contentDescription = null, tint = tint, modifier = Modifier.size(19.dp))
            Text(
                text = label,
                color = tint,
                fontSize = 10.5.sp,
                fontWeight = if (selected) FontWeight.Bold else FontWeight.Medium,
            )
        }
    }
}

/** Switching tabs must not pile screens on the back stack; Back leaves the app. */
private fun NavHostController.navigateTop(route: String) {
    navigate(route) {
        popUpTo(graph.startDestinationId) { saveState = true }
        launchSingleTop = true
        restoreState = true
    }
}

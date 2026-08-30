package es.mojon.soccertime.mobile

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.consumeWindowInsets
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.pager.rememberPagerState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.lifecycle.repeatOnLifecycle
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
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalResources
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import es.mojon.soccertime.core.data.FavoritesTransfer
import es.mojon.soccertime.core.data.FontScale
import es.mojon.soccertime.core.playback.LinkSharing
import es.mojon.soccertime.core.playback.PlayResult
import es.mojon.soccertime.core.ui.AgendaFilter
import es.mojon.soccertime.core.ui.AgendaIntent
import es.mojon.soccertime.core.ui.EventLinks
import es.mojon.soccertime.core.ui.FavoritesIntent
import es.mojon.soccertime.core.ui.ManageIntent
import es.mojon.soccertime.core.ui.Palette
import es.mojon.soccertime.core.ui.SoccertimeIcons
import es.mojon.soccertime.mobile.ui.AGENDA_PAGE
import es.mojon.soccertime.mobile.ui.AgendaScreen
import es.mojon.soccertime.mobile.ui.FAVORITES_PAGE
import es.mojon.soccertime.mobile.ui.FavoritesScreen
import es.mojon.soccertime.mobile.ui.HomePager
import es.mojon.soccertime.mobile.ui.LinksSheet
import es.mojon.soccertime.mobile.ui.SECTION_COUNT
import es.mojon.soccertime.mobile.ui.ManageFavoritesScreen
import es.mojon.soccertime.mobile.ui.NoHandlerDialog
import es.mojon.soccertime.mobile.ui.theme.SoccertimeTheme
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class MainActivity : ComponentActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val graph = (application as SoccertimeApplication).graph
        setContent { SoccertimeTheme { Soccertime(Models(graph, this)) } }
    }
}

private object Routes {
    const val HOME = "home"
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
    // Chosen on the favourites screen, applied on the agenda: two sections with two view
    // models, so it is held above both rather than passed between them.
    var narrowing: AgendaFilter? by remember { mutableStateOf(null) }
    val pagerState = rememberPagerState(initialPage = FAVORITES_PAGE) { SECTION_COUNT }

    val copied = stringResource(R.string.link_copied)

    // The chosen size multiplies the density's own `fontScale`, so every sp in the app moves
    // together and the system's accessibility setting is composed with rather than fought.
    val fontScale by models.settings.fontScale.collectAsStateWithLifecycle(initialValue = FontScale.MEDIUM)
    val density = LocalDensity.current

    CompositionLocalProvider(
        LocalDensity provides Density(density.density, density.fontScale * fontScale.factor),
    ) {
    Scaffold(
        containerColor = MaterialTheme.colorScheme.background,
        bottomBar = {
            val entry by navController.currentBackStackEntryAsState()
            if (entry?.destination?.route != Routes.MANAGE) {
                BottomBar(selected = pagerState.currentPage) { page ->
                    // Tapping the tab you are already on means "show me the agenda", not
                    // "show me the one team I pressed a crest for ten seconds ago".
                    if (page == AGENDA_PAGE && pagerState.currentPage == AGENDA_PAGE) narrowing = null
                    scope.launch { pagerState.animateScrollToPage(page) }
                }
            }
        },
        snackbarHost = { SnackbarHost(snackbars) },
    ) { padding ->
        NavHost(
            navController = navController,
            startDestination = Routes.HOME,
            modifier = Modifier.padding(padding).consumeWindowInsets(padding),
        ) {
            composable(Routes.HOME) {
                HomePager(
                    state = pagerState,
                    modifier = Modifier.fillMaxSize(),
                    favorites = {
                        val favorites =
                            viewModel<es.mojon.soccertime.core.ui.FavoritesViewModel>(factory = models.favorites)
                        val state by favorites.uiState.collectAsStateWithLifecycle()
                        val following by models.following.collectAsStateWithLifecycle(
                            initialValue = es.mojon.soccertime.core.data.Following(),
                        )
                        OnResumed { favorites.onIntent(FavoritesIntent.Resumed) }

                        FavoritesScreen(
                            state = state,
                            following = following,
                            fontScale = fontScale,
                            onIntent = favorites::onIntent,
                            onFontScale = { chosen -> scope.launch { models.settings.setFontScale(chosen) } },
                            onEdit = { navController.navigate(Routes.MANAGE) },
                            onBrowseAgenda = { scope.launch { pagerState.animateScrollToPage(AGENDA_PAGE) } },
                            onOpen = { showing = favorites.linksFor(it.id) },
                            onNarrow = {
                                narrowing = it
                                scope.launch { pagerState.animateScrollToPage(AGENDA_PAGE) }
                            },
                        )
                    },
                    agenda = {
                        val agenda = viewModel<es.mojon.soccertime.core.ui.AgendaViewModel>(factory = models.agenda)
                        val state by agenda.uiState.collectAsStateWithLifecycle()
                        OnResumed { agenda.onIntent(AgendaIntent.Resumed) }
                        LaunchedEffect(narrowing) { agenda.onIntent(AgendaIntent.Narrow(narrowing)) }

                        // BACK undoes the filter before it leaves the section, so the press
                        // that arrived here from a crest is the press that leaves — rather
                        // than dropping the reader into the whole two-day agenda, a screen
                        // they never asked for. Only while this page is the one on screen: a
                        // pager keeps its neighbour composed mid-gesture.
                        BackHandler(enabled = narrowing != null && pagerState.currentPage == AGENDA_PAGE) {
                            narrowing = null
                        }

                        AgendaScreen(
                            state = state,
                            onIntent = { intent ->
                                if (intent is AgendaIntent.Narrow) narrowing = intent.filter
                                agenda.onIntent(intent)
                            },
                            onOpen = { showing = agenda.linksFor(it.id) },
                            dayLabel = models.dayLabel,
                        )
                    },
                )
            }

            composable(Routes.MANAGE) {
                val manage = viewModel<es.mojon.soccertime.core.ui.ManageFavoritesViewModel>(factory = models.manage)
                val state by manage.uiState.collectAsStateWithLifecycle()

                val resources = LocalResources.current
                val exportDone = stringResource(R.string.export_done)
                val exportFailed = stringResource(R.string.export_failed)
                val importFailed = stringResource(R.string.import_failed)

                // Both dialogs are the system's own, so the app never touches a path it was
                // not handed, and the answer arrives as a URI or as null when dismissed.
                val exporter = rememberLauncherForActivityResult(
                    ActivityResultContracts.CreateDocument("application/json"),
                ) { destination ->
                    destination?.let { uri ->
                        scope.launch {
                            val wrote = withContext(Dispatchers.IO) {
                                runCatching {
                                    context.contentResolver.openOutputStream(uri)?.use {
                                        it.write(manage.exportPayload().encodeToByteArray())
                                    } != null
                                }.getOrDefault(false)
                            }
                            snackbars.showSnackbar(if (wrote) exportDone else exportFailed)
                        }
                    }
                }
                val importer = rememberLauncherForActivityResult(
                    ActivityResultContracts.OpenDocument(),
                ) { source ->
                    source?.let { uri ->
                        scope.launch {
                            val text = withContext(Dispatchers.IO) {
                                runCatching {
                                    context.contentResolver.openInputStream(uri)?.use {
                                        it.readBytes().decodeToString()
                                    }
                                }.getOrNull()
                            }
                            val summary = text?.let { manage.importPayload(it) }
                            snackbars.showSnackbar(
                                summary?.let {
                                    resources.getString(
                                        R.string.import_result,
                                        it.total,
                                        it.added,
                                        it.alreadyFollowed,
                                    )
                                } ?: importFailed,
                            )
                        }
                    }
                }

                ManageFavoritesScreen(
                    state = state,
                    onIntent = manage::onIntent,
                    onBack = { navController.popBackStack() },
                    onExport = { exporter.launch(FavoritesTransfer.SUGGESTED_FILE_NAME) },
                    // Downloads and messengers hand JSON over with generic types as often as
                    // the right one, and a filter that excludes them excludes the very file
                    // this exists to read back.
                    onImport = {
                        importer.launch(arrayOf("application/json", "application/octet-stream", "text/plain"))
                    },
                )
            }
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
private fun BottomBar(selected: Int, onSelect: (Int) -> Unit) {
    Row(
        // `fillMaxWidth`, not `fillMaxSize(fraction = 0f)`, which is what this said: that
        // takes zero per cent of BOTH dimensions, and the `height` below only put one of them
        // back. The bar was sixty-six points tall and nothing wide — present, laid out, and
        // invisible — which left the Agenda tab unreachable on a phone.
        Modifier
            .fillMaxWidth()
            .background(Color(Palette.HEADER))
            .windowInsetsPadding(WindowInsets.navigationBars)
            .height(66.dp),
    ) {
        BottomItem(
            label = stringResource(R.string.tab_favorites),
            icon = SoccertimeIcons.Star,
            selected = selected == FAVORITES_PAGE,
            modifier = Modifier.weight(1f),
        ) { onSelect(FAVORITES_PAGE) }

        BottomItem(
            label = stringResource(R.string.tab_agenda),
            icon = SoccertimeIcons.Calendar,
            selected = selected == AGENDA_PAGE,
            modifier = Modifier.weight(1f),
        ) { onSelect(AGENDA_PAGE) }
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
    // `fillMaxHeight` is what makes the alignment mean anything.
    //
    // Without it this box wraps its content — thirty-seven points of icon, gap and label — and
    // the row lays that out with its own default, which is top. So the group sat flush against
    // the bar's upper edge with the indicator on the very first row of pixels, and the fifty-three
    // points below it read as a bar with nothing in the bottom half. Setting `contentAlignment`
    // alone changes nothing, because a box the size of its content has no room to align within.
    //
    // Given the room, bottom is the right end to rest on. The bar paints itself edge to edge and
    // then holds the gesture strip — twenty-four points on this phone, measured — below its own
    // height, so what the eye reads as "the bar" is taller than the box these items live in.
    // Centring would leave the group half that strip above the painted middle at *any* height:
    // for h points of bar the group's centre is h / 2 while the painted centre is h / 2 + 12,
    // which is why making the bar taller was the wrong instinct and would have widened the gap
    // rather than closed it. Resting on the floor puts the centre within half a point of the
    // painted one and still leaves twelve points of clearance above the gesture strip.
    Box(
        modifier.fillMaxHeight().clickable(onClick = onClick),
        contentAlignment = Alignment.BottomCenter,
    ) {
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
            Modifier.padding(bottom = TAB_GROUP_FOOT),
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

/** What the tab group rests on, so its centre lands on the painted bar's centre. */
private val TAB_GROUP_FOOT = 3.dp

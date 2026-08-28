package es.mojon.soccertime.tv

import android.content.Context
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import es.mojon.soccertime.core.AppGraph
import es.mojon.soccertime.core.playback.Playback
import es.mojon.soccertime.core.playback.SystemIntentLauncher
import es.mojon.soccertime.core.ui.AgendaViewModel
import es.mojon.soccertime.core.ui.EventPresenter
import es.mojon.soccertime.core.ui.FavoritesViewModel
import java.time.LocalDateTime
import java.time.format.DateTimeFormatter
import java.util.Locale

/**
 * The television's wiring, and the same view models the phone uses.
 *
 * That is the point of `:core` and it is worth saying once: nothing about which events are
 * shown, when they are reloaded, or what a row says is decided twice. Only the drawing is.
 *
 * There is no `ManageFavoritesViewModel` here, and not because the television cannot follow
 * anything: it can, from the menu button on any event. What it has no use for is that view
 * model's search, which needs a keyboard.
 */
class TvModels(private val graph: AppGraph, context: Context) {

    private val presenter = EventPresenter(graph.times)

    val following = graph.favorites.following

    val favoritesStore = graph.favorites

    val playback = Playback(SystemIntentLauncher(context))

    val favorites: ViewModelProvider.Factory = viewModelFactory {
        initializer {
            FavoritesViewModel(
                events = graph.events,
                presenter = presenter,
                favorites = graph.favorites.favorites,
            )
        }
    }

    val agenda: ViewModelProvider.Factory = viewModelFactory {
        initializer {
            AgendaViewModel(
                events = graph.events,
                presenter = presenter,
                favorites = graph.favorites.favorites,
            )
        }
    }

    /** A television shows the time; there is no status bar here to carry it. */
    fun now(): String = LocalDateTime.now().format(CLOCK)

    private companion object {
        val CLOCK: DateTimeFormatter =
            DateTimeFormatter.ofPattern("EEE d MMM · HH:mm", Locale.forLanguageTag("es-ES"))
    }
}

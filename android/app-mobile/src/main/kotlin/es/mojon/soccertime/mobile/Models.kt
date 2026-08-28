package es.mojon.soccertime.mobile

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
import es.mojon.soccertime.core.ui.ManageFavoritesViewModel

/**
 * How a screen gets its view model.
 *
 * A factory apiece rather than a framework: there are three of them, they take what the graph
 * already holds, and the only thing worth stating is which. Playback takes the activity's
 * context so the chooser, when one is raised, appears over this app rather than behind it.
 */
class Models(graph: AppGraph, context: Context) {

    private val presenter = EventPresenter(graph.times)

    val following = graph.favorites.following

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

    val manage: ViewModelProvider.Factory = viewModelFactory {
        initializer { ManageFavoritesViewModel(catalog = graph.catalog, store = graph.favorites) }
    }
}

package es.mojon.soccertime.mobile

import android.app.Application
import coil3.ImageLoader
import coil3.PlatformContext
import coil3.SingletonImageLoader
import coil3.network.okhttp.OkHttpNetworkFetcherFactory
import coil3.request.crossfade
import es.mojon.soccertime.core.AppGraph

/**
 * Holds the one graph, and points Coil at the same HTTP client the API uses.
 *
 * Sharing the client is not tidiness: a crest is served from the same origin over the same
 * chain, so it needs the same bundled trust anchors — an image loader with a client of its own
 * would fail every load on the Fire TV while the JSON beside it succeeded.
 */
class SoccertimeApplication : Application(), SingletonImageLoader.Factory {

    val graph: AppGraph by lazy { AppGraph.from(this) }

    override fun newImageLoader(context: PlatformContext): ImageLoader =
        ImageLoader.Builder(context)
            .components { add(OkHttpNetworkFetcherFactory(callFactory = { graph.client })) }
            .crossfade(true)
            .build()
}

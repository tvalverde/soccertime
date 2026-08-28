package es.mojon.soccertime.core.data

import es.mojon.soccertime.core.model.EventDto
import es.mojon.soccertime.core.model.Page
import es.mojon.soccertime.core.network.ApiResult
import es.mojon.soccertime.core.network.SoccertimeApi
import es.mojon.soccertime.core.network.SoccertimeApi.Companion.MAX_PAGE_SIZE
import es.mojon.soccertime.core.network.safeCall

/**
 * Every read of the agenda goes through here.
 *
 * Pages are asked for by number rather than by following `Page.next`: DRF builds that URL
 * from the request it saw, and behind the proxy that is a path without the `/soccertime`
 * prefix the site answers on — a client that followed it verbatim would walk off the site.
 */
class EventsRepository(private val api: SoccertimeApi) {

    suspend fun upcoming(page: Int = FIRST_PAGE): ApiResult<Page<EventDto>> = safeCall {
        api.events(
            todayOnwards = true,
            date = null,
            search = null,
            watchable = null,
            ordering = null,
            page = page.takeIf { it != FIRST_PAGE },
            pageSize = MAX_PAGE_SIZE,
        )
    }

    suspend fun onDate(
        date: String,
        search: String? = null,
        watchableOnly: Boolean = false,
        page: Int = FIRST_PAGE,
    ): ApiResult<Page<EventDto>> = safeCall {
        api.events(
            todayOnwards = null,
            date = date,
            search = search?.takeIf { it.isNotBlank() },
            watchable = true.takeIf { watchableOnly },
            ordering = null,
            page = page.takeIf { it != FIRST_PAGE },
            pageSize = MAX_PAGE_SIZE,
        )
    }

    companion object {
        const val FIRST_PAGE: Int = 1
    }
}

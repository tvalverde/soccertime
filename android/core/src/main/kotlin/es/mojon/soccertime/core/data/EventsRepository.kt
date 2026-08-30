package es.mojon.soccertime.core.data

import es.mojon.soccertime.core.model.EventDto
import es.mojon.soccertime.core.model.Page
import es.mojon.soccertime.core.network.ApiResult
import es.mojon.soccertime.core.network.SoccertimeApi
import es.mojon.soccertime.core.network.SoccertimeApi.Companion.MAX_PAGE_SIZE
import es.mojon.soccertime.core.network.safeCall
import java.time.LocalDate

/**
 * One day of the agenda, and how it should be narrowed.
 *
 * A value type rather than six positional arguments, because the listing is asked for twice
 * per load — once for today and once for yesterday — differing in two fields, and a call
 * whose arguments are `(date, null, false, null, 42, true, 1)` is one nobody can read.
 */
data class AgendaQuery(
    val date: String,
    val search: String? = null,
    val watchableOnly: Boolean = false,
    val team: Int? = null,
    val competition: Int? = null,
    /**
     * Ask for the end of the day first.
     *
     * Only yesterday uses this, and it is not a preference. A page holds a hundred and a busy
     * day can carry more, so ascending order would spend the page on the small hours and drop
     * the evening — which is precisely the part of yesterday that is still worth watching at
     * midnight, and the only reason yesterday is fetched at all. The caller reverses it.
     */
    val newestFirst: Boolean = false,
    val page: Int = EventsRepository.FIRST_PAGE,
)

/**
 * Every read of the agenda goes through here.
 *
 * An interface and not just the class below, because what the view models are worth testing
 * for is how often they ask and what they do when the answer does not come — and neither can
 * be arranged through a real HTTP client without turning a unit test into an integration one.
 */
interface EventsRepository {

    /** One page of the events between two local days, both included. */
    suspend fun upcoming(from: LocalDate, until: LocalDate, page: Int = FIRST_PAGE): ApiResult<Page<EventDto>>

    suspend fun onDate(query: AgendaQuery): ApiResult<Page<EventDto>>

    companion object {
        const val FIRST_PAGE: Int = 1

        /** What `ordering=-date` is called here, so the string lives in one place. */
        const val NEWEST_FIRST: String = "-date"
    }
}

/**
 * Pages are asked for by number rather than by following `Page.next`: DRF builds that URL from
 * the request it saw, and behind the proxy that is a path without the `/soccertime` prefix the
 * site answers on — a client that followed it verbatim would walk off the site.
 */
class ApiEventsRepository(private val api: SoccertimeApi) : EventsRepository {

    override suspend fun upcoming(from: LocalDate, until: LocalDate, page: Int): ApiResult<Page<EventDto>> =
        safeCall {
            api.events(
                date = null,
                dateFrom = from.toString(),
                dateTo = until.toString(),
                search = null,
                watchable = null,
                team = null,
                competition = null,
                ordering = null,
                page = page.takeIf { it != EventsRepository.FIRST_PAGE },
                pageSize = MAX_PAGE_SIZE,
            )
        }

    override suspend fun onDate(query: AgendaQuery): ApiResult<Page<EventDto>> = safeCall {
        api.events(
            date = query.date,
            dateFrom = null,
            dateTo = null,
            search = query.search?.takeIf { it.isNotBlank() },
            watchable = true.takeIf { query.watchableOnly },
            team = query.team,
            competition = query.competition,
            ordering = EventsRepository.NEWEST_FIRST.takeIf { query.newestFirst },
            page = query.page.takeIf { it != EventsRepository.FIRST_PAGE },
            pageSize = MAX_PAGE_SIZE,
        )
    }
}

package es.mojon.soccertime.core.data

import es.mojon.soccertime.core.model.CompetitionDto
import es.mojon.soccertime.core.model.Page
import es.mojon.soccertime.core.model.TeamDto
import es.mojon.soccertime.core.network.ApiResult
import es.mojon.soccertime.core.network.SoccertimeApi
import es.mojon.soccertime.core.network.SoccertimeApi.Companion.MAX_PAGE_SIZE
import es.mojon.soccertime.core.network.safeCall

/** The two directories a reader picks favourites from. */
interface CatalogRepository {

    suspend fun teams(search: String?, page: Int = EventsRepository.FIRST_PAGE): ApiResult<Page<TeamDto>>

    suspend fun competitions(
        search: String?,
        page: Int = EventsRepository.FIRST_PAGE,
    ): ApiResult<Page<CompetitionDto>>
}

class ApiCatalogRepository(private val api: SoccertimeApi) : CatalogRepository {

    override suspend fun teams(search: String?, page: Int): ApiResult<Page<TeamDto>> = safeCall {
        api.teams(
            search = search?.takeIf { it.isNotBlank() },
            page = page.takeIf { it != EventsRepository.FIRST_PAGE },
            pageSize = PAGE_SIZE,
        )
    }

    override suspend fun competitions(search: String?, page: Int): ApiResult<Page<CompetitionDto>> =
        safeCall {
            api.competitions(
                search = search?.takeIf { it.isNotBlank() },
                page = page.takeIf { it != EventsRepository.FIRST_PAGE },
                pageSize = PAGE_SIZE,
            )
        }

    companion object {
        /**
         * Smaller than the events listing's hundred. There are 4,796 teams and a reader
         * scrolling a search result reads the first few; fetching the API's maximum would
         * spend bandwidth and a crest download apiece on rows nobody reaches.
         */
        const val PAGE_SIZE: Int = 40
    }
}

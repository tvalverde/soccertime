package es.mojon.soccertime.core.network

import es.mojon.soccertime.core.model.CompetitionDto
import es.mojon.soccertime.core.model.EventDto
import es.mojon.soccertime.core.model.Page
import es.mojon.soccertime.core.model.TeamDto
import retrofit2.http.GET
import retrofit2.http.Query

/**
 * The three listings this app reads.
 *
 * No parameter carries a default value: Retrofit builds the implementation with a dynamic
 * proxy and never runs the synthetic method Kotlin generates for defaults, so one would be
 * silently dropped from the query rather than applied. Callers pass every argument.
 */
interface SoccertimeApi {

    @GET("events/")
    suspend fun events(
        @Query("today_onwards") todayOnwards: Boolean?,
        @Query("date") date: String?,
        @Query("search") search: String?,
        @Query("watchable") watchable: Boolean?,
        @Query("ordering") ordering: String?,
        @Query("page") page: Int?,
        @Query("page_size") pageSize: Int,
    ): Page<EventDto>

    @GET("teams/")
    suspend fun teams(
        @Query("search") search: String?,
        @Query("page") page: Int?,
        @Query("page_size") pageSize: Int,
    ): Page<TeamDto>

    @GET("competitions/")
    suspend fun competitions(
        @Query("search") search: String?,
        @Query("page") page: Int?,
        @Query("page_size") pageSize: Int,
    ): Page<CompetitionDto>

    companion object {
        /**
         * What `Pages.max_page_size` allows, and therefore the fewest requests a day of the
         * agenda can be fetched in. The rate limit is thirty a minute per address, shared by
         * every device on the same connection, so page size is what keeps a session cheap.
         */
        const val MAX_PAGE_SIZE: Int = 100
    }
}

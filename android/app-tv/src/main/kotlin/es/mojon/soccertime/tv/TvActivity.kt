package es.mojon.soccertime.tv

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.produceState
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.tv.material3.Text
import es.mojon.soccertime.core.AppGraph
import es.mojon.soccertime.core.model.EventDto
import es.mojon.soccertime.core.network.ApiError
import es.mojon.soccertime.core.network.ApiResult
import es.mojon.soccertime.core.ui.Palette

/**
 * The walking skeleton on the television.
 *
 * Same purpose as the phone's, and the one that actually matters: the handshake with
 * www.mojon.es anchors at a root Android 7.1 may not carry, and the Fire TV Stick 4K is the
 * only place that can be found out. The outer padding is the overscan margin — 48x27 dp —
 * because a television crops what is drawn to the edge.
 */
class TvActivity : ComponentActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val graph = AppGraph.from(applicationContext)
        setContent { SkeletonAgenda(graph) }
    }
}

@Composable
private fun SkeletonAgenda(graph: AppGraph) {
    val state by produceState<ApiResult<List<EventDto>>?>(initialValue = null, graph) {
        value = when (val result = graph.events.upcoming()) {
            is ApiResult.Success -> ApiResult.Success(result.value.results)
            is ApiResult.Failure -> result
        }
    }

    Column(
        Modifier
            .fillMaxSize()
            .background(Color(Palette.BACKGROUND))
            .padding(horizontal = OVERSCAN_HORIZONTAL, vertical = OVERSCAN_VERTICAL),
    ) {
        Text(
            text = stringResource(R.string.app_name),
            color = Color(Palette.ON_BACKGROUND_VARIANT),
            fontSize = 30.sp,
            fontWeight = FontWeight.Bold,
            modifier = Modifier.padding(bottom = 16.dp),
        )

        when (val current = state) {
            null -> Text(stringResource(R.string.loading), color = Color(Palette.ON_BACKGROUND_MUTED))
            is ApiResult.Failure -> Text(
                text = describe(current.error),
                color = Color(Palette.DANGER),
            )
            is ApiResult.Success -> LazyColumn(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                items(current.value, key = EventDto::id) { EventRow(it) }
            }
        }
    }
}

@Composable
private fun EventRow(event: EventDto) {
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
        Text(
            text = event.date.substringAfter('T').take(TIME_LENGTH),
            color = Color(Palette.PRIMARY),
            fontSize = 22.sp,
            fontWeight = FontWeight.Bold,
            modifier = Modifier.padding(end = 18.dp),
        )
        Column {
            Text(
                text = event.title ?: event.name.orEmpty(),
                color = Color(Palette.ON_BACKGROUND),
                fontSize = 18.sp,
            )
            Text(
                text = event.competition.name,
                color = Color(Palette.ON_BACKGROUND_VARIANT),
                fontSize = 13.sp,
            )
        }
    }
}

@Composable
private fun describe(error: ApiError): String = when (error) {
    is ApiError.Offline -> stringResource(R.string.error_offline)
    is ApiError.RateLimited -> stringResource(R.string.error_rate_limited)
    is ApiError.BadRequest -> error.message
    is ApiError.Http -> stringResource(R.string.error_http, error.code)
    is ApiError.Unexpected -> stringResource(R.string.error_unexpected)
}

private val OVERSCAN_HORIZONTAL = 48.dp
private val OVERSCAN_VERTICAL = 27.dp
private const val TIME_LENGTH = 5

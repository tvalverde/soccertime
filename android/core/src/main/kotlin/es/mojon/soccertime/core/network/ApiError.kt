package es.mojon.soccertime.core.network

import java.io.IOException
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import retrofit2.HttpException
import retrofit2.Response

/** Everything a call to the API can do other than answer. */
sealed interface ApiError {
    /**
     * Thirty a minute in the application and sixty at the proxy. Which one refused decides
     * what the body is, so the header is what gets believed.
     */
    data class RateLimited(val retryAfterSeconds: Long?) : ApiError

    /** A filter the API could not parse. It names the parameter, so the message is shown. */
    data class BadRequest(val message: String) : ApiError

    data class Http(val code: Int) : ApiError

    /** No answer at all: no route, a refused connection, a handshake that failed. */
    data object Offline : ApiError

    data class Unexpected(val cause: Throwable) : ApiError
}

sealed interface ApiResult<out T> {
    data class Success<T>(val value: T) : ApiResult<T>

    data class Failure(val error: ApiError) : ApiResult<Nothing>
}

/**
 * Runs one call and turns everything it can throw into a value.
 *
 * The point is that a caller never sees an exception it has to know Retrofit to interpret,
 * and that the two answers with a body worth reading — 400 and 429 — are read here, once.
 */
suspend fun <T> safeCall(block: suspend () -> T): ApiResult<T> =
    try {
        ApiResult.Success(block())
    } catch (e: HttpException) {
        ApiResult.Failure(errorFrom(e))
    } catch (e: IOException) {
        ApiResult.Failure(ApiError.Offline)
    } catch (@Suppress("TooGenericExceptionCaught") e: Exception) {
        ApiResult.Failure(ApiError.Unexpected(e))
    }

internal fun errorFrom(e: HttpException): ApiError {
    val response = e.response()
    return when (e.code()) {
        HTTP_TOO_MANY_REQUESTS -> ApiError.RateLimited(retryAfterSeconds(response))
        HTTP_BAD_REQUEST -> ApiError.BadRequest(badRequestMessage(response) ?: DEFAULT_BAD_REQUEST)
        else -> ApiError.Http(e.code())
    }
}

/**
 * `Retry-After` is the source of truth. Traefik refuses at the edge with a plain-text body
 * and the application refuses with JSON, so anything that parsed the body would be reading
 * one of two formats without knowing which — while both send this header.
 */
private fun retryAfterSeconds(response: Response<*>?): Long? =
    response?.headers()?.get("Retry-After")?.trim()?.toLongOrNull()?.takeIf { it >= 0 }

/**
 * DRF answers a bad filter with `{"<parameter>": "<what was wrong with it>"}`, and the value
 * is a string on some serializers and a list of them on others. Read only when the response
 * says it is JSON: the same status from the proxy is text, and feeding that to the parser
 * would replace a useful message with a parse failure.
 */
private fun badRequestMessage(response: Response<*>?): String? {
    val body = response?.errorBody() ?: return null
    val mediaType = body.contentType() ?: return null
    if (mediaType.subtype != "json") return null

    val parsed =
        runCatching { LENIENT.parseToJsonElement(body.string()) as? JsonObject }.getOrNull()
            ?: return null
    val (field, value) = parsed.entries.firstOrNull() ?: return null
    val text =
        when (value) {
            is JsonPrimitive -> value.content
            is JsonArray -> (value.firstOrNull() as? JsonPrimitive)?.content
            else -> null
        } ?: return null
    return if (field == DETAIL_FIELD) text else "$field: $text"
}

private const val HTTP_BAD_REQUEST = 400
private const val HTTP_TOO_MANY_REQUESTS = 429
private const val DETAIL_FIELD = "detail"
private const val DEFAULT_BAD_REQUEST = "La consulta no es válida."
private val LENIENT = Json { ignoreUnknownKeys = true }

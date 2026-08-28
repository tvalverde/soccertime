package es.mojon.soccertime.core.network

import java.io.File
import java.util.concurrent.TimeUnit
import kotlinx.serialization.json.Json
import okhttp3.Cache
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import retrofit2.Retrofit
import retrofit2.converter.kotlinx.serialization.asConverterFactory

/** How the one HTTP client and the one Retrofit instance are built. */
object Network {

    /**
     * `ignoreUnknownKeys` is what lets an APK survive the API gaining a field, and
     * `coerceInputValues` is what lets it survive one going null: both are ways the server
     * changes under an installation nobody can update, and neither should be a crash.
     */
    val json: Json = Json {
        ignoreUnknownKeys = true
        coerceInputValues = true
        explicitNulls = false
    }

    /**
     * The disk cache is the whole revalidation story. The API answers with an ETag, so a
     * repeat request costs a 304 and no body — which is what keeps a refresh inside a rate
     * limit that counts requests rather than bytes.
     */
    fun okHttp(cacheDirectory: File?): OkHttpClient =
        OkHttpClient.Builder()
            .apply { cacheDirectory?.let { cache(Cache(it, HTTP_CACHE_BYTES)) } }
            .connectTimeout(CONNECT_TIMEOUT_SECONDS, TimeUnit.SECONDS)
            .readTimeout(READ_TIMEOUT_SECONDS, TimeUnit.SECONDS)
            .retryOnConnectionFailure(true)
            .build()

    fun api(baseUrl: String, client: OkHttpClient): SoccertimeApi =
        Retrofit.Builder()
            .baseUrl(baseUrl)
            .client(client)
            .addConverterFactory(json.asConverterFactory(JSON_MEDIA_TYPE))
            .build()
            .create(SoccertimeApi::class.java)

    private const val HTTP_CACHE_BYTES = 8L * 1024 * 1024
    private const val CONNECT_TIMEOUT_SECONDS = 15L
    private const val READ_TIMEOUT_SECONDS = 30L
    private val JSON_MEDIA_TYPE = "application/json".toMediaType()
}

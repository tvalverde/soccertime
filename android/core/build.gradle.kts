import org.jetbrains.kotlin.gradle.dsl.JvmTarget

plugins {
    alias(libs.plugins.android.library)
    alias(libs.plugins.kotlin.serialization)
    // This module declares `@Composable` members — the icon accessors in `ui/`. Without the
    // Compose compiler here they are compiled without the `Composer` parameter the plugin
    // adds, while the applications, which do have it, call them with one. That mismatch is
    // invisible: it builds, it lints, the unit tests never touch Compose, and the app dies
    // on launch with NoSuchMethodError.
    alias(libs.plugins.kotlin.compose)
}

android {
    namespace = "es.mojon.soccertime.core"
    compileSdk = 37

    defaultConfig {
        minSdk = 25

        // Read by `Network.create`. A debug build of either app can be pointed at a local
        // replica by overriding it there; nothing in the code names the host.
        buildConfigField("String", "API_BASE_URL", "\"https://www.mojon.es/soccertime/api/v1/\"")
    }

    buildFeatures {
        buildConfig = true
    }

    compileOptions {
        // `java.time` does not exist on API 25, and every instant this app handles arrives as
        // an ISO-8601 string with an offset. Desugaring is what makes `OffsetDateTime`
        // available down to the Fire TV rather than forcing a second date library.
        isCoreLibraryDesugaringEnabled = true
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

kotlin {
    compilerOptions {
        jvmTarget.set(JvmTarget.JVM_17)
    }
}

// The cache test creates its directory through `java.io.tmpdir`, which points at the
// machine's global temp by default. Scratch space for a unit test belongs under the build
// directory, where `clean` removes it and a sandboxed or read-only /tmp cannot fail it.
tasks.withType<Test>().configureEach {
    systemProperty("java.io.tmpdir", temporaryDir.absolutePath)
}

dependencies {
    coreLibraryDesugaring(libs.desugar.jdk.libs)

    api(platform(libs.compose.bom))
    // Only what `ui/Fonts.kt` and `ui/SoccertimeIcons.kt` need — the two font families and
    // the icon set, declared once so the phone and the television cannot drift apart. The
    // view models beside them import nothing of Compose and must not start: the phone draws
    // with Material 3 and the television with tv-material, and only the drawing differs.
    //
    // `ui` and not `ui-graphics`: as of Compose 1.12 the `graphics.vector` package, and with
    // it `ImageVector`, lives in the former. Both applications carry `ui` regardless, so this
    // adds nothing to either APK.
    api(libs.compose.ui)
    api(libs.compose.ui.text)

    api(libs.androidx.lifecycle.viewmodel)
    api(libs.androidx.datastore.preferences)
    api(libs.kotlinx.coroutines.android)
    api(libs.kotlinx.serialization.json)
    api(libs.retrofit)
    api(libs.okhttp)
    implementation(libs.retrofit.serialization)
    api(libs.androidx.core.ktx)

    testImplementation(libs.junit)
    testImplementation(libs.kotlinx.coroutines.test)
    testImplementation(libs.okhttp.mockwebserver)
    testImplementation(libs.turbine)
}

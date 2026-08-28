import org.jetbrains.kotlin.gradle.dsl.JvmTarget

plugins {
    alias(libs.plugins.android.library)
    alias(libs.plugins.kotlin.serialization)
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
    // The font families, and nothing else of Compose: the view models below stay free of the
    // toolkit, because the phone draws with Material 3 and the television with tv-material.
    api(libs.compose.ui.text)

    api(libs.androidx.lifecycle.viewmodel)
    api(libs.androidx.datastore.preferences)
    api(libs.kotlinx.coroutines.android)
    api(libs.kotlinx.serialization.json)
    api(libs.retrofit)
    api(libs.okhttp)
    implementation(libs.retrofit.serialization)
    implementation(libs.androidx.core.ktx)

    testImplementation(libs.junit)
    testImplementation(libs.kotlinx.coroutines.test)
    testImplementation(libs.okhttp.mockwebserver)
    testImplementation(libs.turbine)
}

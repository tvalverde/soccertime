import org.jetbrains.kotlin.gradle.dsl.JvmTarget

// Signing material never enters the repository. CI writes the keystore from a base64 secret
// into a file and passes its path here; a machine without these variables builds an unsigned
// release, which is deliberate — it makes `assembleRelease` something anybody can run to find
// out whether R8 broke the app, without holding the key.
val releaseKeystore: String? = System.getenv("ANDROID_KEYSTORE_PATH")

plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.compose)
}

android {
    namespace = "es.mojon.soccertime.mobile"
    compileSdk = 37

    defaultConfig {
        // Deliberately different from the television's, so both install side by side on a
        // device that can run either.
        applicationId = "es.mojon.soccertime"
        minSdk = 25
        targetSdk = 37
        versionCode = 1
        versionName = "0.1.0"
    }

    signingConfigs {
        if (releaseKeystore != null) {
            create("release") {
                storeFile = file(releaseKeystore)
                val store = System.getenv("ANDROID_KEYSTORE_PASSWORD")
                storePassword = store
                keyAlias = System.getenv("ANDROID_KEY_ALIAS")
                // A PKCS12 keystore has one password. `keytool` says so outright when asked
                // for two — "Different store and key passwords not supported for PKCS12
                // KeyStores" — and ignores the second, so the key's password *is* the store's.
                // Falling back means forgetting the fourth secret costs nothing rather than
                // failing a release build with an authentication error nobody expects.
                //
                // Blank counts as absent, and that is the whole point: a secret the repository
                // does not hold still reaches the runner, as an environment variable set to the
                // empty string. Only an unset one is null, which is the local case and the one
                // a bare elvis covers — so the fallback this comment promises would have fired
                // on a developer machine and nowhere else.
                keyPassword = System.getenv("ANDROID_KEY_PASSWORD")?.takeIf(String::isNotBlank) ?: store
            }
        }
    }

    buildTypes {
        release {
            signingConfig = signingConfigs.findByName("release")
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro",
            )
        }
    }

    buildFeatures {
        compose = true
    }

    testOptions {
        unitTests {
            // Robolectric inflates real resources — strings, fonts — so the Compose tests
            // assert the texts the reader actually sees, not test doubles of them.
            isIncludeAndroidResources = true
        }
    }

    compileOptions {
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

dependencies {
    implementation(project(":core"))
    coreLibraryDesugaring(libs.desugar.jdk.libs)

    implementation(platform(libs.compose.bom))
    implementation(libs.compose.ui)
    implementation(libs.compose.ui.graphics)
    implementation(libs.compose.foundation)
    implementation(libs.compose.material3)
    implementation(libs.compose.ui.tooling.preview)
    debugImplementation(libs.compose.ui.tooling)

    // Shares the one OkHttp client, so a crest is revalidated against the same cache and over
    // the same trust anchors as the JSON that named it.
    implementation(libs.coil.compose)
    implementation(libs.coil.network.okhttp)

    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.activity.compose)
    implementation(libs.androidx.lifecycle.runtime.compose)
    implementation(libs.androidx.lifecycle.viewmodel.compose)
    implementation(libs.androidx.navigation.compose)

    testImplementation(libs.junit)
    testImplementation(platform(libs.compose.bom))
    testImplementation(libs.robolectric)
    testImplementation(libs.compose.ui.test.junit4)
    // `debugImplementation`, not `testImplementation`: Robolectric launches the harness
    // activity out of the *merged debug manifest*, and a test-classpath library's manifest
    // never merges into it — as testImplementation the activity is unresolvable at runtime.
    debugImplementation(libs.compose.ui.test.manifest)
}

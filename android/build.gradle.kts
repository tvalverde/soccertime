// AGP's built-in Kotlin compiles with whatever Kotlin Gradle plugin is on the buildscript
// classpath, and AGP itself only pulls in an older bundled version. This pin is what makes
// the build use the `kotlin` version the catalog declares.
buildscript {
    dependencies {
        classpath(libs.kotlin.gradle.plugin)
    }
}

// Declared here and applied in the modules, which is what keeps every module on one version
// of each plugin without any of them saying which.
plugins {
    alias(libs.plugins.android.application) apply false
    alias(libs.plugins.android.library) apply false
    alias(libs.plugins.kotlin.compose) apply false
    alias(libs.plugins.kotlin.serialization) apply false
}

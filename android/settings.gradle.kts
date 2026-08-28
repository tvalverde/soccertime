pluginManagement {
    repositories {
        google {
            content {
                includeGroupByRegex("com\\.android.*")
                includeGroupByRegex("com\\.google.*")
                includeGroupByRegex("androidx.*")
            }
        }
        mavenCentral()
        gradlePluginPortal()
    }
}

dependencyResolutionManagement {
    // A module declaring its own repository is how a build starts resolving from somewhere
    // nobody reviewed. Everything comes from these two, named here once.
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
    }
}

rootProject.name = "soccertime-android"

// One shared module and two applications. `:core` holds everything that is not a screen —
// the API, the data layer, the time arithmetic and the view models — so the phone and the
// television disagree about presentation and about nothing else.
include(":core")
include(":app-mobile")
include(":app-tv")

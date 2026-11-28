import java.util.Properties

plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.kotlin.serialization)
    alias(libs.plugins.hilt)
    alias(libs.plugins.ksp)
    alias(libs.plugins.ktlint)
}

val localProps =
    Properties().apply {
        val f = rootProject.file("potatomeet.properties")
        if (f.exists()) f.inputStream().use { load(it) }
    }
val apiBaseUrl =
    (
        localProps.getProperty("API_BASE_URL")
            ?: "https://oranganman.site/v1"
    ).trimEnd('/')

fun propOrEnv(key: String): String? =
    localProps.getProperty(key)?.takeIf { it.isNotBlank() }
        ?: System.getenv(key)?.takeIf { it.isNotBlank() }

val releaseStoreFilePath = propOrEnv("POTATO_MEET_KEYSTORE_PATH")
val releaseStorePassword = propOrEnv("POTATO_MEET_STORE_PASSWORD")
val releaseKeyAlias = propOrEnv("POTATO_MEET_KEY_ALIAS")
val releaseKeyPassword = propOrEnv("POTATO_MEET_KEY_PASSWORD")
val releaseSigningConfigured =
    listOf(
        releaseStoreFilePath,
        releaseStorePassword,
        releaseKeyAlias,
        releaseKeyPassword,
    ).all { !it.isNullOrBlank() }

android {
    namespace = "com.potatomeet.app"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.potatomeet.app"
        minSdk = 26
        targetSdk = 35
        versionCode = 2
        versionName = "0.1.1"
        buildConfigField("String", "API_BASE_URL", "\"$apiBaseUrl\"")
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }

    signingConfigs {
        create("release") {
            if (releaseSigningConfigured) {
                // Properties treat '\' as escapes; prefer forward slashes in potatomeet.properties.
                storeFile = file(releaseStoreFilePath!!.replace('\\', '/'))
                storePassword = releaseStorePassword
                keyAlias = releaseKeyAlias
                keyPassword = releaseKeyPassword
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro",
            )
            signingConfig = signingConfigs.getByName("release")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
    buildFeatures {
        compose = true
        buildConfig = true
    }
    packaging {
        resources {
            excludes += "/META-INF/{AL2.0,LGPL2.1}"
        }
    }
}

dependencies {
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.activity.compose)
    implementation(libs.androidx.lifecycle.runtime.ktx)
    implementation(libs.androidx.lifecycle.viewmodel.compose)
    implementation(libs.androidx.lifecycle.runtime.compose)
    implementation(libs.androidx.navigation.compose)
    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.compose.ui)
    implementation(libs.androidx.compose.ui.tooling.preview)
    implementation(libs.androidx.compose.material3)
    debugImplementation(libs.androidx.compose.ui.tooling)

    implementation(libs.hilt.android)
    ksp(libs.hilt.compiler)
    implementation(libs.hilt.navigation.compose)

    implementation(libs.retrofit)
    implementation(libs.retrofit.kotlinx.serialization)
    implementation(libs.okhttp)
    implementation(libs.okhttp.logging)
    implementation(libs.okhttp.sse)
    implementation(libs.kotlinx.serialization.json)
    implementation(libs.kotlinx.coroutines.android)
    implementation(libs.androidx.datastore.preferences)

    testImplementation(libs.junit)
}

ktlint {
    android.set(true)
    // Face UI dump split keeps original formatting; tighten after screen Routes land.
    ignoreFailures.set(true)
}

gradle.taskGraph.whenReady {
    val needsReleaseSigning =
        allTasks.any { task ->
            task.name.contains("Release", ignoreCase = true) &&
                (
                    task.name.startsWith("assemble") ||
                        task.name.startsWith("bundle") ||
                        task.name.startsWith("package") ||
                        task.name.startsWith("sign")
                )
        }
    if (needsReleaseSigning && !releaseSigningConfigured) {
        throw GradleException(
            "Missing release signing. Set POTATO_MEET_KEYSTORE_PATH, " +
                "POTATO_MEET_STORE_PASSWORD, POTATO_MEET_KEY_ALIAS, " +
                "POTATO_MEET_KEY_PASSWORD in potatomeet.properties or the environment.",
        )
    }
}

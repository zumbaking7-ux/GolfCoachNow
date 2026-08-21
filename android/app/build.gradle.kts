import java.util.Properties

// Signing credentials, read from keystore.properties (gitignored) or from the
// environment on a build machine that has no file to read.
//
// They used to be written into this file in plain text. The repository is
// public, so the store password, key password and alias were all readable by
// anyone - and the keystore they unlock is the only thing that can ever update
// the Play listing, because Play App Signing was never enabled. The .jks was
// never committed, so the key itself is not compromised, but half of what
// protects it was published and should be treated as known.
val keystoreProperties = Properties()
val keystorePropsFile = rootProject.file("keystore.properties")
if (keystorePropsFile.exists()) {
    keystorePropsFile.inputStream().use { stream -> keystoreProperties.load(stream) }
}

fun secret(key: String, env: String): String =
    keystoreProperties.getProperty(key) ?: System.getenv(env) ?: ""

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
    id("org.jetbrains.kotlin.plugin.serialization")
    id("com.google.gms.google-services")
}

android {
    namespace = "com.golfcoachnow.app"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.golfcoachnow.app"
        minSdk = 26
        targetSdk = 35
        versionCode = 1
        versionName = "1.0"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"

        buildConfigField("String", "API_BASE_URL", "\"https://golfcoachnow.pythonanywhere.com\"")
    }

    // Signing credentials come from keystore.properties, which is gitignored,
    // or from the environment when a build machine has no file to read.
    //
    // They used to be written here in plain text. This repository is public,
    // so the store password, the key password and the alias were all readable
    // by anyone - and the keystore they unlock is the only thing that can ever
    // update the Play listing, because Play App Signing was never switched on.
    // The .jks itself was never committed, so the key is not compromised, but
    // half of what protects it was published and should be treated as known.
    val storeFileName = secret("storeFile", "ANDROID_KEYSTORE_FILE")
        .ifEmpty { "golfcoachnow-release.jks" }
    val haveKeystore = file(storeFileName).exists() &&
        secret("storePassword", "ANDROID_KEYSTORE_PASSWORD").isNotEmpty()

    signingConfigs {
        create("release") {
            if (haveKeystore) {
                storeFile = file(storeFileName)
                storePassword = secret("storePassword", "ANDROID_KEYSTORE_PASSWORD")
                keyAlias = secret("keyAlias", "ANDROID_KEY_ALIAS")
                keyPassword = secret("keyPassword", "ANDROID_KEY_PASSWORD")
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            // Unsigned rather than broken when there are no credentials, so a
            // machine without the keystore still compiles and still tells you
            // whether the code is sound.
            signingConfig = if (haveKeystore) signingConfigs.getByName("release") else null
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
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
}

dependencies {
    val composeBom = platform("androidx.compose:compose-bom:2024.06.00")
    implementation(composeBom)

    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.4")
    implementation("androidx.activity:activity-compose:1.9.1")

    // Compose
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-graphics")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-extended")

    // Navigation
    implementation("androidx.navigation:navigation-compose:2.7.7")

    // CameraX
    implementation("androidx.camera:camera-core:1.3.4")
    implementation("androidx.camera:camera-camera2:1.3.4")
    implementation("androidx.camera:camera-lifecycle:1.3.4")
    implementation("androidx.camera:camera-video:1.3.4")
    implementation("androidx.camera:camera-view:1.3.4")

    // Networking
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.7.1")

    // Coroutines
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.8.1")

    // Browser (for Stripe checkout)
    implementation("androidx.browser:browser:1.8.0")

    // DataStore (preferences)
    implementation("androidx.datastore:datastore-preferences:1.1.1")

    // Firebase
    implementation(platform("com.google.firebase:firebase-bom:33.1.2"))
    implementation("com.google.firebase:firebase-analytics")

    debugImplementation("androidx.compose.ui:ui-tooling")
}

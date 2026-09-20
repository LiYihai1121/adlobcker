plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("com.google.devtools.ksp")
}

// release 构建的后端地址：-PbackendBaseUrl=https://your.domain/（须为 https 且以 / 结尾）
val backendBaseUrl: String = (findProperty("backendBaseUrl") as String?)?.trim().orEmpty()
val releaseRequested: Boolean = gradle.startParameter.taskNames.any { it.contains("Release", ignoreCase = true) }

android {
    namespace = "com.ldp.adblocker"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.ldp.adblocker"
        minSdk = 26
        targetSdk = 34
        versionCode = 1
        versionName = "1.0.0"
    }

    buildTypes {
        debug {
            // 模拟器访问宿主机后端（真机调试请改为后端所在局域网 IP，或用 https 后端）
            buildConfigField("String", "BACKEND_BASE_URL", "\"http://10.0.2.2:8000/\"")
        }
        release {
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
            if (releaseRequested && backendBaseUrl.isBlank()) {
                throw GradleException(
                    "release 构建缺少后端地址：请传入 -PbackendBaseUrl=https://your.domain/（必须为 https 且以 / 结尾）"
                )
            }
            if (backendBaseUrl.isNotBlank()) {
                if (!backendBaseUrl.startsWith("https://")) {
                    throw GradleException("backendBaseUrl 必须是 https:// 地址，当前值: $backendBaseUrl")
                }
                if (!backendBaseUrl.endsWith("/")) {
                    throw GradleException("backendBaseUrl 必须以 / 结尾，当前值: $backendBaseUrl")
                }
                buildConfigField("String", "BACKEND_BASE_URL", "\"$backendBaseUrl\"")
            } else {
                // 仅构建 debug 时允许为空，运行时由 BackendApi 给出清晰错误
                buildConfigField("String", "BACKEND_BASE_URL", "\"\"")
            }
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
    buildFeatures {
        viewBinding = true
        buildConfig = true
    }
    testOptions { unitTests { isReturnDefaultValues = true } }
}

dependencies {
    // AndroidX 基础
    implementation("androidx.core:core-ktx:1.12.0")
    implementation("androidx.appcompat:appcompat:1.6.1")
    implementation("androidx.activity:activity-ktx:1.8.2")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.7.0")
    implementation("androidx.lifecycle:lifecycle-viewmodel-ktx:2.7.0")
    implementation("com.google.android.material:material:1.11.0")

    // Room 数据库（本地缓存广告域名/弹窗规则）
    implementation("androidx.room:room-runtime:2.6.1")
    implementation("androidx.room:room-ktx:2.6.1")
    ksp("androidx.room:room-compiler:2.6.1")

    // Retrofit + Moshi（与后端通信）
    implementation("com.squareup.retrofit2:retrofit:2.9.0")
    implementation("com.squareup.retrofit2:converter-moshi:2.9.0")
    implementation("com.squareup.moshi:moshi:1.15.0")
    implementation("com.squareup.moshi:moshi-kotlin:1.15.0")
    implementation("com.squareup.okhttp3:logging-interceptor:4.12.0")

    // 协程
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.7.3")

    // 单元测试
    testImplementation("junit:junit:4.13.2")
}

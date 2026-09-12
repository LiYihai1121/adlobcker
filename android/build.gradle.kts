// 顶层构建文件
plugins {
    id("com.android.application") version "8.2.2" apply false
    id("org.jetbrains.kotlin.android") version "1.9.22" apply false
    id("com.google.devtools.ksp") version "1.9.22-1.0.17" apply false
}

// Gradle Wrapper 配置：国内访问 services.gradle.org 不稳定，使用腾讯镜像并跳过 URL 校验
tasks.wrapper {
    distributionUrl = "https://mirrors.cloud.tencent.com/gradle/gradle-8.5-bin.zip"
    validateDistributionUrl = false
}

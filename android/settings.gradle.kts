pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}
dependencyResolutionManagement {
    // PREFER_SETTINGS：优先使用 settings 仓库，同时兼容用户级 init 脚本
    // （如 F:\All_Data\gradle\init.d\mirrors.gradle 这类「全局切阿里云镜像」配置）。
    // 注意不要用 FAIL_ON_PROJECT_REPOS —— 它会因任何 init 脚本添加仓库而直接构建失败。
    repositoriesMode.set(RepositoriesMode.PREFER_SETTINGS)
    repositories {
        google()
        mavenCentral()
    }
}

rootProject.name = "AdBlocker"
include(":app")

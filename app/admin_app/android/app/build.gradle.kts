plugins {
    id 'com.android.application'
    id 'kotlin-android'
    id 'dev.flutter.flutter-gradle-plugin'
}

android {
    namespace = "com.example.admin_app"
    compileSdk = 34
    defaultConfig {
        applicationId = "com.example.admin_app"
        minSdk = 21
        targetSdk = 34
        versionCode = flutter.versionCode?.toInt() ?: 1
        versionName = flutter.versionName ?: "1.0"
    }
}

flutter {
    source = '../..'
}

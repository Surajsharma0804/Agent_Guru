# GURU Phone Agent ProGuard Rules
# Production-grade security and obfuscation configuration

# Keep application class
-keep public class com.guru.phoneagent.GuruApplication

# Keep all classes with native methods
-keepclasseswithmembernames class * {
    native <methods>;
}

# Keep all enum classes
-keepclassmembers enum * {
    public static **[] values();
    public static ** valueOf(java.lang.String);
}

# Keep Parcelable implementations
-keepclassmembers class * implements android.os.Parcelable {
    public static final ** CREATOR;
}

# Keep Serializable classes
-keepclassmembers class * implements java.io.Serializable {
    static final long serialVersionUID;
    private static final java.io.ObjectStreamField[] serialPersistentFields;
    private void writeObject(java.io.ObjectOutputStream);
    private void readObject(java.io.ObjectInputStream);
    java.lang.Object writeReplace();
    java.lang.Object readResolve();
}

# Kotlinx Serialization
-keepattributes *Annotation*, InnerClasses
-dontnote kotlinx.serialization.AnnotationsKt
-keepclassmembers class kotlinx.serialization.json.** {
    *** Companion;
}
-keepclasseswithmembers class kotlinx.serialization.json.** {
    kotlinx.serialization.KSerializer serializer(...);
}
-keep,includedescriptorclasses class com.guru.phoneagent.**$$serializer { *; }
-keepclassmembers class com.guru.phoneagent.** {
    *** Companion;
}
-keepclasseswithmembers class com.guru.phoneagent.** {
    kotlinx.serialization.KSerializer serializer(...);
}

# Hilt/Dagger
-dontwarn com.google.errorprone.annotations.**
-keep class dagger.hilt.** { *; }
-keep class javax.inject.** { *; }
-keep class * extends dagger.hilt.android.lifecycle.HiltViewModel {
    <init>(...);
}
-keep @dagger.hilt.android.lifecycle.HiltViewModel class * {
    <init>(...);
}

# Compose
-keep class androidx.compose.runtime.** { *; }
-keep class androidx.compose.ui.** { *; }
-keep class androidx.compose.foundation.** { *; }
-keep class androidx.compose.material3.** { *; }
-dontwarn androidx.compose.**

# Ktor Client
-keep class io.ktor.** { *; }
-keep class kotlinx.coroutines.** { *; }
-dontwarn kotlinx.atomicfu.**
-dontwarn io.netty.**
-dontwarn com.typesafe.**
-dontwarn org.slf4j.**

# BouncyCastle Cryptography
-keep class org.bouncycastle.** { *; }
-dontwarn org.bouncycastle.**
-dontwarn javax.naming.**

# Biometric
-keep class androidx.biometric.** { *; }

# Camera and ML Kit
-keep class androidx.camera.** { *; }
-keep class com.google.mlkit.** { *; }
-dontwarn com.google.android.gms.**

# Security Crypto
-keep class androidx.security.crypto.** { *; }

# Logback
-keep class ch.qos.logback.** { *; }
-dontwarn ch.qos.logback.**
-dontwarn org.codehaus.janino.**

# Remove logging in release builds for security
-assumenosideeffects class android.util.Log {
    public static boolean isLoggable(java.lang.String, int);
    public static int v(...);
    public static int i(...);
    public static int w(...);
    public static int d(...);
    public static int e(...);
}

# Remove debug logging
-assumenosideeffects class kotlin.jvm.internal.Intrinsics {
    static void checkParameterIsNotNull(java.lang.Object, java.lang.String);
}

# Security: Remove stack traces in release
-keepattributes !SourceFile,!LineNumberTable

# Aggressive obfuscation for security
-repackageclasses 'com.guru.phoneagent.obfuscated'
-allowaccessmodification
-mergeinterfacesaggressively

# Keep only essential attributes for security
-keepattributes Signature,RuntimeVisibleAnnotations,AnnotationDefault

# Remove unused code aggressively
-dontwarn **
-ignorewarnings
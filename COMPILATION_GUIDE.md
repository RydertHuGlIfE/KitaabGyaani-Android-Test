# KitaabGyaani Android Compilation Guide

This guide details the optimized steps to build and install the KitaabGyaani Android application.

---

## Prerequisites
Ensure you have the following installed on your system:
* **OpenJDK 17:** Required by Gradle 8.5.
* **Android Debug Bridge (ADB):** For installing the APK on your device.

---

## Compilation Pipeline

### Step 1: Sync Workspace to Native Partition
NTFS partitions can suffer from file locking and performance overhead during Gradle compilation. We sync the workspace to a native Linux partition (`ext4`) for high-speed builds.

Run this command from the project root (`/run/media/Ryder/Coding/AndroidIQOO/`):
```bash
rsync -av --exclude="venv" --exclude=".git" --exclude=".gradle" --exclude=".gradle_home" /run/media/Ryder/Coding/AndroidIQOO/ /home/Ryder/android_build/
```

### Step 2: Navigate to Native Android Directory
```bash
cd /home/Ryder/android_build/android
```

### Step 3: Compile the Debug APK
Build the debug version using the optimized flags to avoid JVM/WatchFS memory leaks and locks:
```bash
JAVA_HOME=/usr/lib/jvm/java-17-openjdk ./gradlew --no-daemon --no-watch-fs assembleDebug
```

### Step 4: Install APK to iQOO Device
Ensure USB Debugging is enabled on your iQOO device and it is connected, then run:
```bash
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

## Troubleshooting

### Gradle Daemon Locks / Freeze
If Gradle hangs at `ExtractAarTransform`, run the build with the `--no-daemon` and `--no-watch-fs` flags to clean up hanging processes:
```bash
JAVA_HOME=/usr/lib/jvm/java-17-openjdk ./gradlew --no-daemon --no-watch-fs assembleDebug
```

### Kill Remaining Daemons
If you still face lock issues, force terminate all existing Gradle daemons:
```bash
pkill -f gradle
```

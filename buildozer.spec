[app]
# Application identity
title = مربی جدول تناوبی
package.name = periodictrainer
package.domain = org.example
version = 1.0.0
android.numeric_version = 10000000
icon.filename = %(source.dir)s/data/icon.png

# The Buildozer entry point and HTML page are staged separately so the existing
# root-level legacy main.py is never overwritten.
source.dir = android_project
source.include_exts = py,html,css,js,png,jpg,kv,atlas
source.exclude_dirs = __pycache__,.git,.buildozer,bin

# Kivy owns the Android lifecycle; PyJNIus creates the native WebView.
requirements = python3,kivy,pyjnius
orientation = portrait
fullscreen = 1

# Fonts/app content are bundled. INTERNET serves the loopback page and optional
# HTTPS links; REQUEST_INSTALL_PACKAGES is needed for the user-confirmed APK flow.
android.permissions = INTERNET,REQUEST_INSTALL_PACKAGES
android.gradle_dependencies = androidx.core:core:1.15.0
android.enable_androidx = True
android.add_resources = %(source.dir)s/data/update_file_paths.xml:xml/update_file_paths.xml
p4a.hook = %(source.dir)s/p4a_hook.py
android.api = 36
android.minapi = 23
android.ndk = 29
android.archs = arm64-v8a, armeabi-v7a
android.private_storage = True
android.accept_sdk_license = True
p4a.branch = develop

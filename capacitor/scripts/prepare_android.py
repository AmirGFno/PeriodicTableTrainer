#!/usr/bin/env python3
"""Install the project's native Capacitor bridge into a freshly generated Android app."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ANDROID = ROOT / "android"
CONFIG = json.loads((ROOT / "capacitor.config.json").read_text(encoding="utf-8"))
APP_ID = CONFIG["appId"]
APP_VERSION = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))["version"]
VERSION_CODE = os.environ.get("GITHUB_RUN_NUMBER", "1")
if not VERSION_CODE.isdigit() or int(VERSION_CODE) < 1:
    raise SystemExit("GITHUB_RUN_NUMBER must be a positive integer")

manifest_path = ANDROID / "app/src/main/AndroidManifest.xml"
gradle_path = ANDROID / "app/build.gradle"
main_candidates = list((ANDROID / "app/src/main/java").rglob("MainActivity.java"))
if not manifest_path.is_file() or not gradle_path.is_file() or len(main_candidates) != 1:
    raise SystemExit("Capacitor Android project not found; run `npx cap add android` first")

package_path = Path(*APP_ID.split("."))
java_dir = ANDROID / "app/src/main/java" / package_path
java_dir.mkdir(parents=True, exist_ok=True)
plugin_source = ROOT / "capacitor/native/PeriodicTrainerNativePlugin.java"
plugin_text = plugin_source.read_text(encoding="utf-8")
plugin_text = re.sub(r"(?m)^package [\w.]+;", f"package {APP_ID};", plugin_text, count=1)
(java_dir / "PeriodicTrainerNativePlugin.java").write_text(plugin_text, encoding="utf-8")

main_activity = f'''package {APP_ID};

import android.os.Bundle;
import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {{
    @Override
    public void onCreate(Bundle savedInstanceState) {{
        registerPlugin(PeriodicTrainerNativePlugin.class);
        super.onCreate(savedInstanceState);
    }}
}}
'''
main_candidates[0].write_text(main_activity, encoding="utf-8")

manifest = manifest_path.read_text(encoding="utf-8")
for permission in ("android.permission.INTERNET", "android.permission.REQUEST_INSTALL_PACKAGES"):
    if f'android:name="{permission}"' not in manifest:
        manifest = manifest.replace(
            "<application",
            f'    <uses-permission android:name="{permission}" />\n    <application',
            1,
        )
provider = '''
        <provider
            android:name="androidx.core.content.FileProvider"
            android:authorities="${applicationId}.fileprovider"
            android:exported="false"
            android:grantUriPermissions="true">
            <meta-data
                android:name="android.support.FILE_PROVIDER_PATHS"
                android:resource="@xml/file_paths" />
        </provider>
'''
if "androidx.core.content.FileProvider" not in manifest:
    manifest = manifest.replace("</application>", provider + "    </application>", 1)
manifest_path.write_text(manifest, encoding="utf-8")

xml_dir = ANDROID / "app/src/main/res/xml"
xml_dir.mkdir(parents=True, exist_ok=True)
file_paths = xml_dir / "file_paths.xml"
if not file_paths.is_file():
    file_paths.write_text(
        '''<?xml version="1.0" encoding="utf-8"?>
<paths xmlns:android="http://schemas.android.com/apk/res/android">
</paths>
''',
        encoding="utf-8",
    )
paths_xml = file_paths.read_text(encoding="utf-8")
if 'name="periodic_trainer_updates"' not in paths_xml:
    paths_xml = paths_xml.replace(
        "</paths>", '    <files-path name="periodic_trainer_updates" path="updates/" />\n</paths>'
    )
    file_paths.write_text(paths_xml, encoding="utf-8")

gradle = gradle_path.read_text(encoding="utf-8")
code_pattern = re.compile(r"(?m)^(\s*versionCode\s+)\d+\s*$")
name_pattern = re.compile(r"(?m)^(\s*versionName\s+)[\"'][^\"']*[\"']\s*$")
gradle, code_count = code_pattern.subn(rf"\g<1>{VERSION_CODE}", gradle, count=1)
gradle, name_count = name_pattern.subn(rf'\g<1>"{APP_VERSION}"', gradle, count=1)
if code_count != 1 or name_count != 1:
    raise SystemExit("Could not update app versionCode/versionName in generated app/build.gradle")
if "androidx.core:core:" not in gradle:
    dependency_block = re.search(r"(?m)^dependencies\s*\{", gradle)
    if not dependency_block:
        raise SystemExit("Could not find dependencies block in generated app/build.gradle")
    insert_at = dependency_block.end()
    gradle = gradle[:insert_at] + "\n    implementation 'androidx.core:core:1.13.1'" + gradle[insert_at:]
gradle_path.write_text(gradle, encoding="utf-8")
print(f"Registered PeriodicTrainerNative for {APP_ID}; version {APP_VERSION} ({VERSION_CODE}).")

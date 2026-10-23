#!/usr/bin/env python3
"""Install the project's native Capacitor bridge into a freshly generated Android app."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from PIL import Image

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


def install_launcher_icons() -> None:
    """Install the transparent black-and-orange logo in raster and adaptive Android icon slots."""
    logo_path = ROOT / "app_logo.png"
    if not logo_path.is_file():
        raise SystemExit(f"Android logo is missing: {logo_path}")
    logo = Image.open(logo_path).convert("RGBA")
    alpha_bounds = logo.getchannel("A").getbbox()
    if not alpha_bounds:
        raise SystemExit("Android logo has no visible pixels")
    logo = logo.crop(alpha_bounds)

    resources = ANDROID / "app/src/main/res"
    densities = {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}
    for density, size in densities.items():
        mipmap = resources / f"mipmap-{density}"
        mipmap.mkdir(parents=True, exist_ok=True)
        for filename, safe_fraction in (
            ("ic_launcher.png", 0.90),
            ("ic_launcher_round.png", 0.78),
            ("ic_launcher_foreground.png", 0.66),
        ):
            mark = logo.copy()
            max_side = max(1, round(size * safe_fraction))
            mark.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
            canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            canvas.alpha_composite(mark, ((size - mark.width) // 2, (size - mark.height) // 2))
            canvas.save(mipmap / filename, format="PNG", optimize=True)

    adaptive_dir = resources / "mipmap-anydpi-v26"
    adaptive_dir.mkdir(parents=True, exist_ok=True)
    adaptive_xml = '''<?xml version="1.0" encoding="utf-8"?>
<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">
    <background android:drawable="@color/periodictrainer_icon_background" />
    <foreground android:drawable="@mipmap/ic_launcher_foreground" />
</adaptive-icon>
'''
    for filename in ("ic_launcher.xml", "ic_launcher_round.xml"):
        (adaptive_dir / filename).write_text(adaptive_xml, encoding="utf-8")
    values_dir = resources / "values"
    values_dir.mkdir(parents=True, exist_ok=True)
    (values_dir / "periodictrainer_icon_background.xml").write_text(
        '''<?xml version="1.0" encoding="utf-8"?>
<resources><color name="periodictrainer_icon_background">#00000000</color></resources>
''',
        encoding="utf-8",
    )


install_launcher_icons()

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
print(f"Registered PeriodicTrainerNative and transparent launcher icons for {APP_ID}; version {APP_VERSION} ({VERSION_CODE}).")

"""Patch the generated Android manifest to register the update FileProvider.

The hook runs before Gradle packages the APK. The provider is scoped to the
app's private files directory and is required for safe APK installation on
Android 7+ (file:// URIs are intentionally not used).
"""
from pathlib import Path
import re


def before_apk_build(toolchain):
    manifest = Path(toolchain._dist.dist_dir) / "src" / "main" / "AndroidManifest.xml"
    if not manifest.is_file():
        raise FileNotFoundError(f"python-for-android manifest not found: {manifest}")
    text = manifest.read_text(encoding="utf-8")

    # The bundled HTML is served over loopback HTTP; enable it for this app.
    cleartext_attr = re.compile(r'android:usesCleartextTraffic\s*=\s*["\'][^"\']*["\']')
    if cleartext_attr.search(text):
        text = cleartext_attr.sub('android:usesCleartextTraffic="true"', text, count=1)
    else:
        text, count = re.subn(r"<application\b", '<application android:usesCleartextTraffic="true"', text, count=1)
        if count != 1:
            raise RuntimeError("Could not find the <application> tag in generated manifest")

    if "${applicationId}.updatesprovider" not in text:
        provider_xml = '''
        <provider
            android:name="androidx.core.content.FileProvider"
            android:authorities="${applicationId}.updatesprovider"
            android:exported="false"
            android:grantUriPermissions="true">
            <meta-data
                android:name="android.support.FILE_PROVIDER_PATHS"
                android:resource="@xml/update_file_paths" />
        </provider>
'''
        text, count = re.subn(r"</application>", provider_xml + "    </application>", text, count=1)
        if count != 1:
            raise RuntimeError("Could not append FileProvider to the generated manifest")

    manifest.write_text(text, encoding="utf-8")

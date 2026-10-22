"""Kivy/PyJNIus Android WebView app with durable records and APK updater."""
from __future__ import annotations

import hashlib
import json
import os
import re
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
from typing import Any
from urllib.parse import urlparse, urlsplit
from urllib.request import Request, urlopen

from kivy.app import App
from kivy.clock import Clock
from kivy.utils import platform

from update_config import APP_VERSION, MAX_UPDATE_BYTES, REQUEST_TIMEOUT_SECONDS, VERSION_URL

APP_TITLE = "مربی جدول تناوبی"
LOCAL_HOST = "127.0.0.1"
LOCAL_PORT = 8765  # Fixed origin is required for persistent WebView localStorage.
MAX_BACKUP_BYTES = 2 * 1024 * 1024


def _version_tuple(value: str) -> tuple[int, ...]:
    match = re.fullmatch(r"v?(\d+(?:\.\d+){0,4})", str(value or "").strip(), re.I)
    if not match:
        raise ValueError(f"Invalid version string: {value!r}")
    parts = tuple(int(part) for part in match.group(1).split("."))
    return parts + (0,) * (5 - len(parts))


def _https_url(value: Any) -> str:
    url = str(value or "").strip()
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("Update URLs must be valid HTTPS URLs")
    return url


def fetch_version_manifest() -> dict[str, Any]:
    request = Request(VERSION_URL, headers={"User-Agent": f"PeriodicTableTrainer/{APP_VERSION}"})
    with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        raw = response.read(1024 * 1024 + 1)
    if len(raw) > 1024 * 1024:
        raise ValueError("version.json is unexpectedly large")
    manifest = json.loads(raw.decode("utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("version.json must be a JSON object")
    _version_tuple(manifest.get("latest_version", ""))
    return manifest


class QuietPageHandler(SimpleHTTPRequestHandler):
    """Serve the bundled page and same-origin updater/backup endpoints."""

    def log_message(self, format, *args):  # noqa: A002 - stdlib hook signature
        pass

    def _send_json(self, value: Any, status: int = 200) -> None:
        body = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/api/restore":
            self._send_json(self.server.app_instance.restore_data())
            return
        if path == "/api/version":
            self._send_json(self.server.app_instance.check_update())
            return
        super().do_GET()

    def do_POST(self):
        path = urlsplit(self.path).path
        if path == "/api/backup":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > MAX_BACKUP_BYTES:
                    self._send_json({"ok": False, "error": "invalid payload size"}, 413)
                    return
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                ok = self.server.app_instance.backup_data(payload)
                self._send_json({"ok": bool(ok)}, 200 if ok else 400)
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
                self._send_json({"ok": False, "error": "invalid JSON"}, 400)
            return
        if path == "/api/update":
            result = self.server.app_instance.update_android()
            self._send_json(result, 200 if result.get("ok") else 400)
            return
        self.send_error(404)


class AppHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, handler, app_instance):
        super().__init__(address, handler)
        self.app_instance = app_instance


class PeriodicTableApp(App):
    title = APP_TITLE

    def build(self):
        # Kivy supplies the lifecycle; the native Android WebView is installed
        # into the Activity after the first frame.
        return None

    def on_start(self):
        self._server = None
        self._server_thread = None
        self.webview = None
        self._backup_lock = threading.Lock()
        self._update_lock = threading.Lock()
        self._update_running = False
        self._pending_apk: Path | None = None
        self._pending_update_version: str | None = None
        self._opening_install_settings = False
        self._installer_launched = False
        self._start_local_server()
        Clock.schedule_once(lambda _dt: self._show_android_webview(), 0.25)

    def backup_data(self, payload: Any) -> bool:
        """Persist the full app state to Kivy's private user_data_dir."""
        try:
            value = json.loads(payload) if isinstance(payload, str) else payload
            if not isinstance(value, dict):
                return False
            destination = Path(self.user_data_dir) / "records.json"
            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary = destination.with_suffix(".json.tmp")
            encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
            with self._backup_lock:
                temporary.write_text(encoded, encoding="utf-8")
                os.replace(temporary, destination)
            return True
        except (OSError, TypeError, ValueError, AttributeError):
            return False

    def restore_data(self):
        """Return a parsed state object or None if no valid backup exists."""
        destination = Path(self.user_data_dir) / "records.json"
        try:
            with self._backup_lock:
                value = json.loads(destination.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else None
        except (OSError, TypeError, ValueError, AttributeError):
            return None

    def check_update(self) -> dict[str, Any]:
        """Fetch and validate the Android entry in the hosted version manifest."""
        try:
            manifest = fetch_version_manifest()
            latest = str(manifest["latest_version"])
            available = _version_tuple(latest) > _version_tuple(APP_VERSION)
            result = {
                "available": available,
                "current_version": APP_VERSION,
                "latest_version": latest,
                "notes": str(manifest.get("notes", "")),
            }
            if available:
                result["android_url"] = _https_url(manifest.get("android_url"))
            return result
        except Exception as exc:
            return {"error": f"بررسی نسخه ناموفق بود: {exc}"}

    def update_android(self) -> dict[str, Any]:
        """Start a background APK download, then request Android's installer."""
        if platform != "android":
            return {"ok": False, "error": "به‌روزرسانی APK فقط روی Android در دسترس است."}
        with self._update_lock:
            if self._update_running:
                return {"ok": True, "message": "دانلود به‌روزرسانی در حال انجام است."}
            self._update_running = True
            self._installer_launched = False
        threading.Thread(target=self._download_android_update, name="android-updater", daemon=True).start()
        return {"ok": True}

    def _notify_progress(self, percent: int, message: str) -> None:
        self._evaluate_js(f"window.setUpdateProgress({int(percent)},{json.dumps(message, ensure_ascii=False)})")

    def _notify_error(self, message: str) -> None:
        self._evaluate_js(f"window.showUpdateError({json.dumps(message, ensure_ascii=False)})")

    def _notify_finished(self, message: str) -> None:
        self._evaluate_js(f"window.finishUpdateProgress({json.dumps(message, ensure_ascii=False)})")

    def _evaluate_js(self, script: str) -> None:
        def run(_dt):
            try:
                if self.webview is not None:
                    self.webview.evaluateJavascript(script, None)
            except Exception:
                pass
        try:
            Clock.schedule_once(run, 0)
        except Exception:
            pass

    def _download_android_update(self) -> None:
        temporary: Path | None = None
        try:
            self._notify_progress(0, "در حال دانلود بروزرسانی... لطفاً برنامه را نبندید")
            manifest = fetch_version_manifest()
            latest = str(manifest["latest_version"])
            if _version_tuple(latest) <= _version_tuple(APP_VERSION):
                raise ValueError("نسخهٔ جدیدی برای Android موجود نیست.")
            url = _https_url(manifest.get("android_url"))
            updates_dir = Path(self.user_data_dir) / "updates"
            updates_dir.mkdir(parents=True, exist_ok=True)
            apk_path = updates_dir / "PeriodicTableTrainer.apk"

            # If a prior download is waiting for the install permission, reuse it.
            if not (self._pending_apk == apk_path and self._pending_update_version == latest and apk_path.is_file()):
                temporary = apk_path.with_suffix(".apk.part")
                request = Request(url, headers={"User-Agent": f"PeriodicTableTrainer/{APP_VERSION}"})
                digest = hashlib.sha256()
                with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                    length = int(response.headers.get("Content-Length", "0") or 0)
                    if length > MAX_UPDATE_BYTES:
                        raise ValueError("APK exceeds the configured maximum download size")
                    received = 0
                    with temporary.open("wb") as output:
                        while True:
                            block = response.read(256 * 1024)
                            if not block:
                                break
                            received += len(block)
                            if received > MAX_UPDATE_BYTES:
                                raise ValueError("APK exceeds the configured maximum download size")
                            output.write(block)
                            digest.update(block)
                            percent = int(received * 100 / length) if length else 0
                            self._notify_progress(min(percent, 99), "در حال دانلود بروزرسانی... لطفاً برنامه را نبندید")
                if received < 4:
                    raise ValueError("Downloaded APK is empty or incomplete")
                with temporary.open("rb") as source:
                    if source.read(4) != b"PK\x03\x04":
                        raise ValueError("Downloaded file is not a valid APK/ZIP")
                expected = manifest.get("android_sha256")
                if expected and digest.hexdigest().lower() != str(expected).lower():
                    raise ValueError("SHA-256 check failed for the downloaded APK")
                os.replace(temporary, apk_path)

            self._pending_apk = apk_path
            self._pending_update_version = latest
            self._notify_progress(100, "دانلود کامل شد؛ در حال آماده‌سازی نصب...")
            Clock.schedule_once(lambda _dt: self._install_or_request_permission(), 0)
        except Exception as exc:
            if temporary:
                temporary.unlink(missing_ok=True)
            self._notify_error(f"دانلود به‌روزرسانی Android ناموفق بود: {exc}")
        finally:
            with self._update_lock:
                self._update_running = False

    def _install_or_request_permission(self):
        if platform != "android" or not self._pending_apk or self._installer_launched:
            return
        from android.runnable import run_on_ui_thread
        from jnius import autoclass

        @run_on_ui_thread
        def run_install_flow():
            try:
                PythonActivity = autoclass("org.kivy.android.PythonActivity")
                Intent = autoclass("android.content.Intent")
                Uri = autoclass("android.net.Uri")
                BuildVersion = autoclass("android.os.Build$VERSION")
                activity = PythonActivity.mActivity
                if int(BuildVersion.SDK_INT) >= 26 and not activity.getPackageManager().canRequestPackageInstalls():
                    self._opening_install_settings = True
                    self._notify_finished(
                        "برای نصب نسخه جدید، لطفاً به برنامه اجازه نصب از منابع ناشناس (Install from Unknown Sources) را بدهید. پس از بازگشت، نصب ادامه می‌یابد."
                    )
                    settings_intent = Intent("android.settings.MANAGE_UNKNOWN_APP_SOURCES")
                    settings_intent.setData(Uri.parse("package:" + str(activity.getPackageName())))
                    settings_intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                    activity.startActivity(settings_intent)
                    return
                self._launch_apk_installer(activity, Intent)
            except Exception as exc:
                self._notify_error(f"باز کردن نصب‌کنندهٔ Android ممکن نشد: {exc}")

        run_install_flow()

    def _launch_apk_installer(self, activity, Intent) -> None:
        from jnius import autoclass
        File = autoclass("java.io.File")
        FileProvider = autoclass("androidx.core.content.FileProvider")
        apk_file = File(str(self._pending_apk))
        authority = str(activity.getPackageName()) + ".updatesprovider"
        uri = FileProvider.getUriForFile(activity, authority, apk_file)
        install_intent = Intent("android.intent.action.INSTALL_PACKAGE")
        install_intent.setDataAndType(uri, "application/vnd.android.package-archive")
        install_intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_ACTIVITY_NEW_TASK)
        self._installer_launched = True
        self._opening_install_settings = False
        try:
            activity.startActivity(install_intent)
        except Exception:
            self._installer_launched = False
            raise
        self._notify_finished("نصب‌کنندهٔ Android باز شد؛ تأیید نصب را انجام دهید.")

    def on_resume(self):
        # If the user just granted the unknown-source permission in Settings,
        # continue directly to the installer. If not, leave the modal actionable.
        if getattr(self, "_pending_apk", None) and platform == "android" and not self._installer_launched:
            Clock.schedule_once(lambda _dt: self._resume_pending_install(), 0.35)
        return True

    def _resume_pending_install(self):
        if not self._pending_apk or platform != "android":
            return
        try:
            from jnius import autoclass
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            BuildVersion = autoclass("android.os.Build$VERSION")
            activity = PythonActivity.mActivity
            if int(BuildVersion.SDK_INT) < 26 or activity.getPackageManager().canRequestPackageInstalls():
                self._install_or_request_permission()
            elif self._opening_install_settings:
                self._opening_install_settings = False
                self._notify_finished(
                    "برای نصب نسخهٔ جدید، اجازهٔ Install from Unknown Sources را فعال کنید و دوباره «دانلود و نصب» را بزنید. فایل دانلودشده حفظ شده است."
                )
        except Exception:
            pass

    def _start_local_server(self):
        html_file = Path(__file__).resolve().parent / "mobile_index.html"
        if not html_file.is_file():
            raise FileNotFoundError(f"Bundled mobile_index.html is missing: {html_file}")
        handler = partial(QuietPageHandler, directory=str(html_file.parent))
        self._server = AppHTTPServer((LOCAL_HOST, LOCAL_PORT), handler, self)
        self._server_thread = threading.Thread(target=self._server.serve_forever, name="periodic-table-local-http", daemon=True)
        self._server_thread.start()

    def _show_android_webview(self):
        if platform != "android":
            raise RuntimeError("mobile_app.py is intended to run inside an Android APK.")
        from android.runnable import run_on_ui_thread
        from jnius import autoclass

        @run_on_ui_thread
        def install_webview():
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            WebView = autoclass("android.webkit.WebView")
            WebViewClient = autoclass("android.webkit.WebViewClient")
            View = autoclass("android.view.View")
            LayoutParams = autoclass("android.view.ViewGroup$LayoutParams")
            WindowManagerLayoutParams = autoclass("android.view.WindowManager$LayoutParams")
            activity = PythonActivity.mActivity
            view = WebView(activity)
            settings = view.getSettings()
            settings.setJavaScriptEnabled(True)
            settings.setDomStorageEnabled(True)
            settings.setDatabaseEnabled(True)
            settings.setAllowFileAccess(False)
            settings.setAllowContentAccess(False)
            settings.setSupportZoom(False)
            settings.setBuiltInZoomControls(False)
            view.setWebViewClient(WebViewClient())
            view.setLayoutParams(LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.MATCH_PARENT))
            activity.getWindow().addFlags(WindowManagerLayoutParams.FLAG_KEEP_SCREEN_ON)
            decor = activity.getWindow().getDecorView()
            immersive = (
                View.SYSTEM_UI_FLAG_FULLSCREEN | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                | View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY | View.SYSTEM_UI_FLAG_LAYOUT_STABLE
                | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
            )
            decor.setSystemUiVisibility(immersive)
            activity.setContentView(view)
            self.webview = view
            view.loadUrl(f"http://{LOCAL_HOST}:{LOCAL_PORT}/mobile_index.html")

        install_webview()

    def on_stop(self):
        server = getattr(self, "_server", None)
        if server is not None:
            server.shutdown()
            server.server_close()
            self._server = None


if __name__ == "__main__":
    PeriodicTableApp().run()

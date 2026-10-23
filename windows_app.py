"""Windows desktop wrapper, durable backup API, and self-updater."""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import webview

from update_config import APP_VERSION, MAX_UPDATE_BYTES, REQUEST_TIMEOUT_SECONDS, VERSION_URL

APP_NAME = "PeriodicTableTrainer"
EXE_NAME = "PeriodicTableTrainer.exe"
HTTP_PORT = 8765  # Stable origin/profile for WebView localStorage.
_BACKUP_LOCK = threading.Lock()


def _version_tuple(value: str) -> tuple[int, ...]:
    match = re.fullmatch(r"v?(\d+(?:\.\d+){0,4})", str(value or "").strip(), re.I)
    if not match:
        raise ValueError(f"Invalid version string: {value!r}")
    parts = tuple(int(part) for part in match.group(1).split("."))
    return parts + (0,) * (5 - len(parts))


def _https_url(value: Any) -> str:
    url = str(value or "").strip()
    if urlparse(url).scheme != "https" or not urlparse(url).netloc:
        raise ValueError("Update URLs must be valid HTTPS URLs")
    return url


def app_data_dir() -> Path:
    root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    path = root / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def backup_file() -> Path:
    return app_data_dir() / "records.json"


def bundled_file(filename: str) -> Path:
    """Resolve a resource embedded by PyInstaller (or beside the source script)."""
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return root / filename


def app_directory() -> Path:
    """Return the directory beside the executable, or beside the source script."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _html_version_text(path: Path) -> str | None:
    """Return the validated user-interface version embedded in an HTML file."""
    try:
        text = path.read_text(encoding="utf-8")
        match = re.search(r"const\s+CURRENT_APP_VERSION\s*=\s*['\"]([^'\"]+)['\"]", text)
        if not match:
            return None
        version = match.group(1)
        _version_tuple(version)
        return version
    except (OSError, UnicodeError, ValueError):
        return None


def _html_version(path: Path) -> tuple[int, ...] | None:
    """Read the interface version embedded in an external HTML candidate."""
    version = _html_version_text(path)
    return _version_tuple(version) if version else None


def windows_html_file() -> Path:
    """Use the newest interface from writable AppData, the install folder, or bundle."""
    candidates = (
        app_data_dir() / "windows_index.html",
        app_directory() / "windows_index.html",
        bundled_file("windows_index.html"),
    )
    existing = [path for path in candidates if path.is_file()]
    if not existing:
        raise FileNotFoundError("windows_index.html was not found in AppData, beside the app, or inside the bundle")
    versioned = [(version, -index, path) for index, path in enumerate(existing) if (version := _html_version(path)) is not None]
    if versioned:
        return max(versioned)[2]
    return existing[0]


def current_windows_version() -> str:
    """Report the version of the HTML actually selected by this installation.

    The EXE can legitimately be older than an HTML-only in-app update. Using
    APP_VERSION here would make the updater keep reporting the stale EXE version.
    """
    try:
        return _html_version_text(windows_html_file()) or APP_VERSION
    except (OSError, RuntimeError, ValueError):
        return APP_VERSION


def fetch_version_manifest() -> dict[str, Any]:
    request = Request(VERSION_URL, headers={"User-Agent": f"{APP_NAME}/{APP_VERSION}"})
    with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        raw = response.read(1024 * 1024 + 1)
    if len(raw) > 1024 * 1024:
        raise ValueError("version.json is unexpectedly large")
    manifest = json.loads(raw.decode("utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("version.json must contain a JSON object")
    _version_tuple(manifest.get("latest_version", ""))
    return manifest


def _update_batch_script(working_dir: str, exe_path: str) -> str:
    """Generate a guarded AppData HTML swap and verified app restart batch."""
    return f"""@echo off
chcp 65001 >NUL
setlocal EnableExtensions
cd /d "%~dp0"

rem Give the WebView time to close, then force-close any remaining instance.
timeout /t 3 /nobreak >NUL
taskkill /f /im {EXE_NAME} >NUL 2>&1
set "RETRIES=0"
:wait_for_exit
tasklist /FI "IMAGENAME eq {EXE_NAME}" 2>NUL | find /I "{EXE_NAME}" >NUL
if errorlevel 1 goto process_closed
set /a RETRIES+=1
if %RETRIES% GEQ 20 goto exit_timeout
timeout /t 1 /nobreak >NUL
goto wait_for_exit

:exit_timeout
echo The old app did not exit; update swap was cancelled.
goto cleanup

:process_closed
if not exist "new_index.html" goto launch_fallback
if exist "windows_index_old.html" del /q "windows_index_old.html"
if not exist "windows_index.html" goto move_downloaded_html
ren "windows_index.html" "windows_index_old.html"
if errorlevel 1 goto restore_old

:move_downloaded_html
ren "new_index.html" "windows_index.html"
if errorlevel 1 goto restore_old
if not exist "windows_index.html" goto restore_old

rem Start the EXE again; it selects the highest-version HTML from AppData.
start "" /D "{working_dir}" "{exe_path}"
set "RETRIES=0"
:wait_for_new_app
timeout /t 1 /nobreak >NUL
tasklist /FI "IMAGENAME eq {EXE_NAME}" 2>NUL | find /I "{EXE_NAME}" >NUL
if not errorlevel 1 goto update_started
set /a RETRIES+=1
if %RETRIES% GEQ 20 goto new_app_failed
goto wait_for_new_app

:update_started
if exist "windows_index_old.html" del /q "windows_index_old.html"
goto cleanup

:new_app_failed
echo The updated app did not start; restoring the previous HTML.
taskkill /f /im {EXE_NAME} >NUL 2>&1
timeout /t 2 /nobreak >NUL

:restore_old
if exist "windows_index_old.html" (
  if exist "windows_index.html" del /q "windows_index.html"
  ren "windows_index_old.html" "windows_index.html"
)
if exist "new_index.html" del /q "new_index.html"
goto launch_fallback

:launch_fallback
rem If no AppData HTML exists, the installed/bundled copy remains available.
if exist "{exe_path}" start "" /D "{working_dir}" "{exe_path}"

:cleanup
del /q "%~f0"
endlocal
"""


class BackupApi:
    """Methods exposed to JavaScript by pywebview."""

    def __init__(self) -> None:
        self.restart_requested = False
        self._update_lock = threading.Lock()
        self._update_running = False
        self._window = None

    def backup_data(self, payload: str) -> bool:
        """Atomically save the complete app state to AppData/records.json."""
        try:
            value = json.loads(payload) if isinstance(payload, str) else payload
            if not isinstance(value, dict):
                return False
            encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
            destination = backup_file()
            temporary = destination.with_suffix(".json.tmp")
            with _BACKUP_LOCK:
                temporary.write_text(encoded, encoding="utf-8")
                os.replace(temporary, destination)
            return True
        except (OSError, TypeError, ValueError):
            return False

    def restore_data(self) -> str:
        """Return the saved state as JSON, or an empty string if unavailable."""
        try:
            with _BACKUP_LOCK:
                raw = backup_file().read_text(encoding="utf-8")
            value: Any = json.loads(raw)
            return json.dumps(value, ensure_ascii=False) if isinstance(value, dict) else ""
        except (OSError, TypeError, ValueError):
            return ""

    def check_update(self) -> dict[str, Any]:
        """Fetch version.json and report whether a newer Windows release exists."""
        try:
            manifest = fetch_version_manifest()
            latest = str(manifest["latest_version"])
            current = current_windows_version()
            available = _version_tuple(latest) > _version_tuple(current)
            result = {
                "available": available,
                "current_version": current,
                "latest_version": latest,
                "notes": str(manifest.get("notes", "")),
            }
            if available:
                result["windows_html_url"] = _https_url(manifest.get("windows_html_url"))
            return result
        except Exception as exc:
            return {"error": f"بررسی نسخه ناموفق بود: {exc}"}

    def _eval_js(self, script: str) -> None:
        try:
            window = self._window or webview.active_window()
            if window:
                window.evaluate_js(script)
        except Exception:
            pass

    def _progress(self, percent: int, message: str) -> None:
        self._eval_js(f"window.setUpdateProgress({int(percent)},{json.dumps(message, ensure_ascii=False)})")

    def _error(self, message: str) -> None:
        self._eval_js(f"window.showUpdateError({json.dumps(message, ensure_ascii=False)})")

    def update_windows(self) -> dict[str, Any]:
        """Download the replaceable HTML, then hand off its swap to update.bat."""
        if not getattr(sys, "frozen", False):
            return {"ok": False, "error": "به‌روزرسانی خودکار فقط در نسخهٔ EXE فعال است."}
        with self._update_lock:
            if self._update_running:
                return {"ok": True, "message": "دانلود به‌روزرسانی در حال انجام است."}
            self._update_running = True
        threading.Thread(target=self._update_worker, name="windows-updater", daemon=True).start()
        return {"ok": True}

    def _download_html(self, url: str, destination: Path, expected_sha256: str | None) -> None:
        """Download and validate only the replaceable Windows HTML interface."""
        request = Request(url, headers={"User-Agent": f"{APP_NAME}/{APP_VERSION}"})
        temporary = destination.with_suffix(destination.suffix + ".part")
        digest = hashlib.sha256()
        try:
            with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                length = int(response.headers.get("Content-Length", "0") or 0)
                if length > MAX_UPDATE_BYTES:
                    raise ValueError("HTML update exceeds the configured maximum download size")
                received = 0
                with temporary.open("wb") as output:
                    while True:
                        block = response.read(256 * 1024)
                        if not block:
                            break
                        received += len(block)
                        if received > MAX_UPDATE_BYTES:
                            raise ValueError("HTML update exceeds the configured maximum download size")
                        output.write(block)
                        digest.update(block)
                        percent = int(received * 100 / length) if length else 0
                        self._progress(min(percent, 99), "در حال دانلود بروزرسانی... لطفاً برنامه را نبندید")
            if received == 0:
                raise ValueError("Downloaded HTML file is empty")
            with temporary.open("rb") as source:
                sample = source.read(64 * 1024).lower()
            if b"<html" not in sample:
                raise ValueError("Downloaded file does not look like a Windows HTML page")
            if expected_sha256 and digest.hexdigest().lower() != str(expected_sha256).lower():
                raise ValueError("SHA-256 check failed for the downloaded HTML file")
            os.replace(temporary, destination)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise

    def _update_worker(self) -> None:
        try:
            self._progress(0, "در حال دانلود بروزرسانی... لطفاً برنامه را نبندید")
            manifest = fetch_version_manifest()
            latest = str(manifest["latest_version"])
            current = current_windows_version()
            if _version_tuple(latest) <= _version_tuple(current):
                raise ValueError("نسخهٔ جدیدی برای ویندوز موجود نیست.")
            url = _https_url(manifest.get("windows_html_url"))
            app_dir = app_directory()
            data_dir = app_data_dir()
            new_html = data_dir / "new_index.html"
            self._download_html(url, new_html, manifest.get("windows_html_sha256"))
            downloaded_version = _html_version_text(new_html)
            if not downloaded_version or _version_tuple(downloaded_version) != _version_tuple(latest):
                new_html.unlink(missing_ok=True)
                raise ValueError("نسخهٔ HTML دانلودشده با version.json یکسان نیست؛ جابه‌جایی لغو شد.")

            # Install folders such as Program Files are protected. Keep the
            # replaceable HTML in per-user AppData, then restart the same EXE.
            bat = data_dir / "update.bat"
            exe_path = str(app_dir / EXE_NAME)
            working_dir = str(app_dir)
            bat.write_text(_update_batch_script(working_dir, exe_path), encoding="utf-8", newline="")
            creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)
            subprocess.Popen(["cmd.exe", "/c", bat.name], cwd=str(data_dir), creationflags=creationflags, close_fds=True)
            self.restart_requested = True
            self._progress(
                100,
                "برنامه برای اعمال تغییرات بسته می‌شود. لطفاً چند لحظه صبر کنید و از بستن پنجره‌های سیاه رنگ خودداری کنید.",
            )
            time.sleep(0.3)
            try:
                (self._window or webview.active_window()).destroy()
            except Exception:
                pass
        except Exception as exc:
            self._error(f"دانلود/نصب به‌روزرسانی ویندوز ناموفق بود: {exc}")
        finally:
            with self._update_lock:
                self._update_running = False


def main() -> None:
    html_file = windows_html_file()
    profile = app_data_dir() / "WebViewProfile"
    profile.mkdir(parents=True, exist_ok=True)
    api = BackupApi()
    window = webview.create_window(
        title="مربی جدول تناوبی",
        url=str(html_file),
        js_api=api,
        width=1280,
        height=850,
        min_size=(900, 650),
        resizable=True,
        background_color="#101827",
    )
    api._window = window
    webview.start(http_server=True, http_port=HTTP_PORT, private_mode=False, storage_path=str(profile), debug=False)
    if api.restart_requested:
        sys.exit(0)


if __name__ == "__main__":
    main()

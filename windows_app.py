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
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return root / filename


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
            available = _version_tuple(latest) > _version_tuple(APP_VERSION)
            result = {
                "available": available,
                "current_version": APP_VERSION,
                "latest_version": latest,
                "notes": str(manifest.get("notes", "")),
            }
            if available:
                result["windows_url"] = _https_url(manifest.get("windows_url"))
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
        """Download the new EXE, then hand off replacement to update.bat."""
        if not getattr(sys, "frozen", False):
            return {"ok": False, "error": "به‌روزرسانی خودکار فقط در نسخهٔ EXE فعال است."}
        with self._update_lock:
            if self._update_running:
                return {"ok": True, "message": "دانلود به‌روزرسانی در حال انجام است."}
            self._update_running = True
        threading.Thread(target=self._update_worker, name="windows-updater", daemon=True).start()
        return {"ok": True}

    def _download_executable(self, url: str, destination: Path, expected_sha256: str | None) -> None:
        request = Request(url, headers={"User-Agent": f"{APP_NAME}/{APP_VERSION}"})
        temporary = destination.with_suffix(destination.suffix + ".part")
        digest = hashlib.sha256()
        try:
            with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                length = int(response.headers.get("Content-Length", "0") or 0)
                if length > MAX_UPDATE_BYTES:
                    raise ValueError("EXE exceeds the configured maximum download size")
                received = 0
                with temporary.open("wb") as output:
                    while True:
                        block = response.read(256 * 1024)
                        if not block:
                            break
                        received += len(block)
                        if received > MAX_UPDATE_BYTES:
                            raise ValueError("EXE exceeds the configured maximum download size")
                        output.write(block)
                        digest.update(block)
                        percent = int(received * 100 / length) if length else 0
                        self._progress(min(percent, 99), "در حال دانلود بروزرسانی... لطفاً برنامه را نبندید")
            if received == 0:
                raise ValueError("Downloaded EXE is empty")
            with temporary.open("rb") as source:
                if source.read(2) != b"MZ":
                    raise ValueError("Downloaded file is not a Windows executable")
            if expected_sha256 and digest.hexdigest().lower() != str(expected_sha256).lower():
                raise ValueError("SHA-256 check failed for the downloaded EXE")
            os.replace(temporary, destination)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise

    def _update_worker(self) -> None:
        try:
            self._progress(0, "در حال دانلود بروزرسانی... لطفاً برنامه را نبندید")
            manifest = fetch_version_manifest()
            latest = str(manifest["latest_version"])
            if _version_tuple(latest) <= _version_tuple(APP_VERSION):
                raise ValueError("نسخهٔ جدیدی برای ویندوز موجود نیست.")
            url = _https_url(manifest.get("windows_url"))
            app_dir = Path(sys.executable).resolve().parent
            new_exe = app_dir / "new_app.exe"
            self._download_executable(url, new_exe, manifest.get("windows_sha256"))

            # The running EXE cannot replace itself. The adjacent BAT waits for
            # this process to close, swaps the file, launches it, then self-deletes.
            bat = app_dir / "update.bat"
            bat.write_text(
                "@echo off\r\n"
                "cd /d \"%~dp0\"\r\n"
                "timeout /t 2 /nobreak > NUL\r\n"
                f"taskkill /f /im \"{EXE_NAME}\" > NUL 2>&1\r\n"
                "timeout /t 1 /nobreak > NUL\r\n"
                f"move /y \"%~dp0new_app.exe\" \"%~dp0{EXE_NAME}\" > NUL\r\n"
                f"start \"\" \"%~dp0{EXE_NAME}\"\r\n"
                "del \"%~f0\"\r\n",
                encoding="ascii",
            )
            creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)
            subprocess.Popen(["cmd.exe", "/c", str(bat)], cwd=str(app_dir), creationflags=creationflags, close_fds=True)
            self.restart_requested = True
            self._progress(100, "به‌روزرسانی آماده است؛ برنامه دوباره اجرا می‌شود.")
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
    html_file = bundled_file("windows_index.html")
    if not html_file.is_file():
        raise FileNotFoundError(f"Missing bundled app page: {html_file}")
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

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


def update_log_file() -> Path:
    """Diagnostics for the in-app updater, written next to the backups."""
    return app_data_dir() / "update.log"


def _append_update_log(message: str) -> None:
    """Best-effort updater diagnostics; never raises into the UI thread."""
    try:
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        with update_log_file().open("a", encoding="utf-8") as log:
            log.write(f"{stamp} {message}\n")
    except OSError:
        pass


def _powershell_executable() -> Path:
    """Locate powershell.exe; fall back to PATH lookup."""
    candidate = (
        Path(os.environ.get("SystemRoot", r"C:\Windows"))
        / "System32"
        / "WindowsPowerShell"
        / "v1.0"
        / "powershell.exe"
    )
    return candidate if candidate.is_file() else Path("powershell.exe")


def _update_powershell_script(working_dir: str, exe_path: str) -> str:
    """Generate the guarded HTML swap/restart helper.

    A batch file cannot be used here: the helper runs detached without a
    console, and ``timeout /t`` fails immediately in that situation, which
    cancelled the swap and relaunched the previous interface. PowerShell
    sleeps do not need a console, and its move/error handling is retried.
    """
    template = r"""$ErrorActionPreference = 'Continue'
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $dir
$log = Join-Path $dir 'update.log'

function Write-UpdateLog([string]$Message) {
    try {
        Add-Content -LiteralPath $log -Value ((Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' ' + $Message) -Encoding UTF8
    } catch {
    }
}

function Get-AppProcess {
    return (Get-Process -Name '__EXE_BASE__' -ErrorAction SilentlyContinue)
}

function Wait-AppExit([int]$TimeoutSeconds) {
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-AppProcess) -and ((Get-Date) -lt $deadline)) {
        Start-Sleep -Milliseconds 250
    }
    return (-not (Get-AppProcess))
}

$target = Join-Path $dir 'windows_index.html'
$newFile = Join-Path $dir 'new_index.html'
$backup = Join-Path $dir 'windows_index_old.html'
$exe = '__EXE_PATH__'
$work = '__WORK_DIR__'

Write-UpdateLog '--- update swap started ---'

if (-not (Wait-AppExit 15)) {
    Write-UpdateLog 'app still running; forcing stop'
    Get-AppProcess | Stop-Process -Force -ErrorAction SilentlyContinue
    if (-not (Wait-AppExit 15)) {
        Write-UpdateLog 'app could not be stopped; swap cancelled'
        Remove-Item -LiteralPath $MyInvocation.MyCommand.Path -Force -ErrorAction SilentlyContinue
        exit 1
    }
}
Write-UpdateLog 'previous instance closed'

if (-not (Test-Path -LiteralPath $newFile)) {
    Write-UpdateLog 'new_index.html is missing; nothing to swap'
    Remove-Item -LiteralPath $MyInvocation.MyCommand.Path -Force -ErrorAction SilentlyContinue
    exit 1
}

$swapped = $false
for ($attempt = 1; $attempt -le 10; $attempt++) {
    try {
        if (Test-Path -LiteralPath $target) {
            Move-Item -LiteralPath $target -Destination $backup -Force
        }
        Move-Item -LiteralPath $newFile -Destination $target -Force
        if (Test-Path -LiteralPath $target) {
            $swapped = $true
            break
        }
    } catch {
        Write-UpdateLog ('swap attempt ' + $attempt + ' failed: ' + $_.Exception.Message)
        Start-Sleep -Milliseconds 500
    }
}

if ($swapped) {
    Write-UpdateLog 'interface swapped in AppData'
} else {
    Write-UpdateLog 'swap failed; keeping the previous interface'
    if ((Test-Path -LiteralPath $backup) -and (-not (Test-Path -LiteralPath $target))) {
        Move-Item -LiteralPath $backup -Destination $target -Force -ErrorAction SilentlyContinue
    }
}

$started = $false
if (Test-Path -LiteralPath $exe) {
    try {
        Start-Process -FilePath $exe -WorkingDirectory $work
        $deadline = (Get-Date).AddSeconds(25)
        while (((Get-Date) -lt $deadline) -and (-not (Get-AppProcess))) {
            Start-Sleep -Milliseconds 250
        }
        $started = [bool](Get-AppProcess)
    } catch {
        Write-UpdateLog ('relaunch failed: ' + $_.Exception.Message)
    }
}

if ($started) {
    Write-UpdateLog 'app relaunched'
    Remove-Item -LiteralPath $backup -Force -ErrorAction SilentlyContinue
} else {
    Write-UpdateLog 'relaunched app did not start; restoring the previous interface'
    try {
        if (Test-Path -LiteralPath $backup) {
            if (Test-Path -LiteralPath $target) {
                Remove-Item -LiteralPath $target -Force
            }
            Move-Item -LiteralPath $backup -Destination $target -Force
        }
    } catch {
        Write-UpdateLog ('restore failed: ' + $_.Exception.Message)
    }
    if (Test-Path -LiteralPath $exe) {
        try {
            Start-Process -FilePath $exe -WorkingDirectory $work
        } catch {
        }
    }
}

Remove-Item -LiteralPath $newFile -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $MyInvocation.MyCommand.Path -Force -ErrorAction SilentlyContinue
"""
    return (
        template.replace("__EXE_BASE__", Path(EXE_NAME).stem)
        .replace("__EXE_PATH__", str(exe_path).replace("'", "''"))
        .replace("__WORK_DIR__", str(working_dir).replace("'", "''"))
    )


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
            # APP_VERSION is baked into the EXE at build time. When it is older
            # than the latest release, the HTML-only in-app update cannot move
            # the shell forward and the fresh installer has to be run once.
            result["shell_version"] = APP_VERSION
            if _version_tuple(latest) > _version_tuple(APP_VERSION):
                result["shell_outdated"] = True
                result["windows_url"] = _https_url(manifest.get("windows_url"))
            return result
        except Exception as exc:
            return {"error": f"بررسی نسخه ناموفق بود: {exc}"}

    def open_download_page(self) -> dict[str, Any]:
        """Open the installer download page in the default browser."""
        try:
            manifest = fetch_version_manifest()
            url = _https_url(manifest.get("windows_url"))
            os.startfile(url)  # type: ignore[attr-defined]
            return {"ok": True}
        except Exception as exc:
            return {"ok": False, "error": f"بازکردن صفحهٔ دانلود ناموفق بود: {exc}"}

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
        """Download the replaceable HTML, then hand its swap to update.ps1."""
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
            script = data_dir / "update.ps1"
            exe_path = str(app_dir / EXE_NAME)
            working_dir = str(app_dir)
            script.write_text(
                _update_powershell_script(working_dir, exe_path), encoding="utf-8-sig", newline="\r\n"
            )
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)
            subprocess.Popen(
                [
                    str(_powershell_executable()),
                    "-NoProfile",
                    "-NonInteractive",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(script),
                ],
                cwd=str(data_dir),
                creationflags=creationflags,
                close_fds=True,
            )
            _append_update_log(f"downloaded HTML {downloaded_version}; restarting via update.ps1")
            self.restart_requested = True
            self._progress(
                100,
                "برنامه برای اعمال تغییرات بسته می‌شود و چند لحظه بعد خودکار باز می‌شود. لطفاً صبر کنید.",
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

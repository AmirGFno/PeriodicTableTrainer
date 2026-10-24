"""Shared update endpoint/version settings for desktop and Android wrappers.

PTT_VERSION_URL can override the public repository manifest URL at runtime.
"""
import os

APP_VERSION = "1.1.15"
VERSION_URL = os.environ.get(
    "PTT_VERSION_URL",
    "https://raw.githubusercontent.com/AmirGFno/PeriodicTableTrainer/main/version.json",
)
REQUEST_TIMEOUT_SECONDS = 30
MAX_UPDATE_BYTES = 500 * 1024 * 1024

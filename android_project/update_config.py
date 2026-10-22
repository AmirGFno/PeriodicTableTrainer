"""Shared update endpoint/version settings for desktop and Android wrappers.

Before publishing, replace the example version.json URL with an HTTPS URL you
control. PTT_VERSION_URL may also override it at runtime for private testing.
"""
import os

APP_VERSION = "1.0.0"
VERSION_URL = os.environ.get(
    "PTT_VERSION_URL",
    "https://example.com/version.json",
)
REQUEST_TIMEOUT_SECONDS = 30
MAX_UPDATE_BYTES = 500 * 1024 * 1024

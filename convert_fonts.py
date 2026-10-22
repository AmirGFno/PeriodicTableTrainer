#!/usr/bin/env python3
"""Inline the four Persian UI fonts into the Windows and Android HTML files.

The checked-in HTML files remain standalone: this script downloads/caches only
build-time source fonts, converts TTF/OTF inputs to WOFF2 when fontTools and
Brotli are installed, then writes data:font/woff2;base64 URLs into each page.
Running it again is safe and refreshes the embedded blocks in place.
"""
from __future__ import annotations

import argparse
import base64
from io import BytesIO
from pathlib import Path
import re
import urllib.request

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "font_sources"
BEGIN = "/* BEGIN EMBEDDED OFFLINE FONTS */"
END = "/* END EMBEDDED OFFLINE FONTS */"
USER_AGENT = "Mozilla/5.0 (compatible; PeriodicTableTrainerFontBuilder/1.0)"

ARABIC_RANGE = (
    "U+0600-06FF,U+0750-077F,U+0870-0891,U+0897-08E1,U+08E3-08FF,"
    "U+200C-200E,U+2010-2011,U+204F,U+2E41,U+FB50-FDFF,"
    "U+FE70-FE74,U+FE76-FEFC"
)
LATIN_RANGE = (
    "U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,"
    "U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,"
    "U+2212,U+2215,U+FEFF,U+FFFD"
)

# Google Fonts files are variable WOFF2 where a weight range is declared.
# Shabnam is obtained from its archived upstream package, which is OFL-licensed.
FONTS = [
    ("Vazirmatn", "400 900", "vazirmatn-arabic.woff2", "https://fonts.gstatic.com/s/vazirmatn/v16/Dxxo8j6PP2D_kU2muijlGMWWMmk.woff2", ARABIC_RANGE),
    ("Vazirmatn", "400 900", "vazirmatn-latin.woff2", "https://fonts.gstatic.com/s/vazirmatn/v16/Dxxo8j6PP2D_kU2muijlHcWW.woff2", LATIN_RANGE),
    ("Estedad", "400 900", "estedad-arabic.woff2", "https://fonts.gstatic.com/s/estedad/v3/QdVWSTk1OgitjvYTJJDEvDlh.woff2", ARABIC_RANGE),
    ("Estedad", "400 900", "estedad-latin.woff2", "https://fonts.gstatic.com/s/estedad/v3/QdVWSTk1OgitjvYTJJXEvA.woff2", LATIN_RANGE),
    ("Lalezar", "400", "lalezar-arabic.woff2", "https://fonts.gstatic.com/s/lalezar/v16/zrfl0HLVx-HwTP82YaL4IxL0.woff2", ARABIC_RANGE),
    ("Lalezar", "400", "lalezar-latin.woff2", "https://fonts.gstatic.com/s/lalezar/v16/zrfl0HLVx-HwTP82Yaf4Iw.woff2", LATIN_RANGE),
    ("Shabnam", "400", "shabnam-regular.woff2", "https://cdn.jsdelivr.net/npm/shabnam-font@5.0.0/dist/Farsi-Digits/Shabnam-FD.woff2", None),
    ("Shabnam", "700", "shabnam-bold.woff2", "https://cdn.jsdelivr.net/npm/shabnam-font@5.0.0/dist/Farsi-Digits/Shabnam-Bold-FD.woff2", None),
]


def fetch(url: str, cache_file: Path, refresh: bool) -> bytes:
    if cache_file.exists() and not refresh:
        return cache_file.read_bytes()
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=45) as response:
        data = response.read()
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_bytes(data)
    return data


def to_woff2(data: bytes, label: str) -> bytes:
    """Return WOFF2 bytes; convert a provided TTF/OTF if needed."""
    if data[:4] == b"wOF2":
        return data
    try:
        from fontTools.ttLib import TTFont
    except ImportError as exc:
        raise RuntimeError(
            f"{label} is not WOFF2. Install conversion support with: "
            "python -m pip install fonttools brotli"
        ) from exc
    font = TTFont(BytesIO(data))
    font.flavor = "woff2"
    output = BytesIO()
    font.save(output)
    return output.getvalue()


def build_css(refresh: bool) -> str:
    rules = [BEGIN, "/* SIL Open Font License (OFL); embedded to permit offline use. */"]
    for family, weight, filename, url, unicode_range in FONTS:
        raw = fetch(url, CACHE / filename, refresh)
        woff2 = to_woff2(raw, filename)
        encoded = base64.b64encode(woff2).decode("ascii")
        range_rule = f"  unicode-range:{unicode_range};\n" if unicode_range else ""
        rules.append(
            "@font-face{\n"
            f"  font-family:'{family}';\n"
            "  font-style:normal;\n"
            f"  font-weight:{weight};\n"
            "  font-display:swap;\n"
            f"  src:url(data:font/woff2;base64,{encoded}) format('woff2');\n"
            f"{range_rule}"
            "}"
        )
    rules.append(END)
    return "\n".join(rules)


def embed_in_html(path: Path, css: str) -> None:
    html = path.read_text(encoding="utf-8")
    # Remove the old online stylesheet, if present.
    html = re.sub(
        r'<link\s+href="https://fonts\.googleapis\.com/css2\?[^\"]+"\s+rel="stylesheet">\s*',
        "",
        html,
        count=1,
    )
    block_pattern = re.compile(re.escape(BEGIN) + r".*?" + re.escape(END), re.S)
    if block_pattern.search(html):
        html = block_pattern.sub(css, html, count=1)
    else:
        html = html.replace("<style>", "<style>\n" + css + "\n", 1)
    path.write_text(html, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="download fresh font source files")
    args = parser.parse_args()
    css = build_css(args.refresh)
    for filename in ("windows_index.html", "mobile_index.html"):
        embed_in_html(ROOT / filename, css)
        print(f"Embedded offline fonts into {filename}")
    print(f"Font source cache: {CACHE}")


if __name__ == "__main__":
    main()

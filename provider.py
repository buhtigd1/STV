#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Scrape IPTV channels from:
https://raw.githubusercontent.com/darkbyteprojects/iptv_png/main/provider_6/sports_channels.json

Output:
    stv.m3u
    stv.log

Features:
    - Generates Kodi-compatible M3U
    - Preserves User-Agent, Referer, Origin headers
    - Adds #KODIPROP for HLS and DASH streams
    - Logs providers and channels processed
"""

import requests
from datetime import datetime

JSON_URL = (
    "https://raw.githubusercontent.com/darkbyteprojects/iptv_png/main/provider_6/sports_channels.json"
)

M3U_FILE = "stv.m3u"
LOG_FILE = "stv.log"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


def log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    line = f"[{timestamp}] {message}"

    print(line)

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def detect_manifest_type(url):
    url = url.lower()

    if ".mpd" in url:
        return "mpd"

    if ".m3u8" in url:
        return "hls"

    return None


def parse_url_and_headers(link):
    if "|" not in link:
        return link.strip(), {}

    stream_url, header_part = link.split("|", 1)

    header_part = header_part.replace("&amp;", "&")

    headers = {}

    for item in header_part.split("&"):
        if "=" in item:
            key, value = item.split("=", 1)
            headers[key.strip()] = value.strip()

    return stream_url.strip(), headers


def build_kodi_headers(headers):
    result = []

    header_map = {
        "user-agent": "User-Agent",
        "User-Agent": "User-Agent",
        "referer": "Referer",
        "Referer": "Referer",
        "origin": "Origin",
        "Origin": "Origin",
    }

    added = set()

    for key, kodi_name in header_map.items():
        if key in headers and kodi_name not in added:
            result.append(f"{kodi_name}={headers[key]}")
            added.add(kodi_name)

    return "&".join(result)


def write_channel(
    playlist,
    group_name,
    logo,
    channel_name,
    stream_url,
    headers,
):
    playlist.write(
        f'#EXTINF:-1 tvg-name="{channel_name}" '
        f'tvg-logo="{logo}" '
        f'group-title="{group_name}",{channel_name}\n'
    )

    manifest = detect_manifest_type(stream_url)

    if manifest:
        playlist.write(
            "#KODIPROP:inputstream=inputstream.adaptive\n"
        )

        playlist.write(
            f"#KODIPROP:inputstream.adaptive.manifest_type={manifest}\n"
        )

    kodi_headers = build_kodi_headers(headers)

    if kodi_headers:
        playlist.write(
            "#KODIPROP:inputstream.adaptive.stream_headers="
            f"{kodi_headers}\n"
        )

    playlist.write(stream_url + "\n\n")


def main():

    open(LOG_FILE, "w").close()

    log("Starting scrape")

    response = requests.get(
        JSON_URL,
        headers=HEADERS,
        timeout=30,
    )

    response.raise_for_status()

    providers = response.json()

    provider_count = 0
    channel_count = 0

    with open(M3U_FILE, "w", encoding="utf-8") as playlist:

        #
        # M3U Header
        #
        playlist.write("#EXTM3U\n\n")

        for provider in providers:

            provider_count += 1

            provider_name = provider.get(
                "title",
                "Unknown"
            )

            provider_logo = provider.get(
                "image",
                ""
            )

            formats = provider.get(
                "formats",
                []
            )

            log(
                f"Provider: {provider_name} "
                f"({len(formats)} channels)"
            )

            for item in formats:

                title = item.get(
                    "title",
                    ""
                ).strip()

                link = item.get(
                    "link",
                    ""
                ).strip()

                if not link:
                    continue

                link = link.replace("&amp;", "&")

                stream_url, stream_headers = (
                    parse_url_and_headers(link)
                )

                write_channel(
                    playlist=playlist,
                    group_name=provider_name,
                    logo=provider_logo,
                    channel_name=title,
                    stream_url=stream_url,
                    headers=stream_headers,
                )

                channel_count += 1

    log(f"Providers processed: {provider_count}")
    log(f"Channels written: {channel_count}")
    log(f"Playlist saved: {M3U_FILE}")
    log("Finished")


if __name__ == "__main__":
    try:
        main()

    except Exception as e:
        log(f"ERROR: {e}")
        raise

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
from datetime import datetime

JSON_URL = "https://raw.githubusercontent.com/darkbyteprojects/iptv_png/main/provider_6/sports_channels.json"

M3U_FILE = "stv.m3u"
LOG_FILE = "stv.log"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


def log(message):
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
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
            k, v = item.split("=", 1)
            headers[k.strip()] = v.strip()

    return stream_url.strip(), headers


def build_kodi_headers(headers):
    result = []

    mapping = {
        "user-agent": "User-Agent",
        "User-Agent": "User-Agent",
        "referer": "Referer",
        "Referer": "Referer",
        "origin": "Origin",
        "Origin": "Origin",
    }

    added = set()

    for source_key, kodi_key in mapping.items():
        value = headers.get(source_key)

        if value and kodi_key not in added:
            result.append(f"{kodi_key}={value}")
            added.add(kodi_key)

    return "&".join(result)


def write_channel(
    playlist,
    provider_name,
    logo,
    channel_name,
    stream_url,
    headers,
    api_key=""
):

    playlist.write(
        f'#EXTINF:-1 '
        f'tvg-name="{channel_name}" '
        f'tvg-logo="{logo}" '
        f'group-title="{provider_name}",'
        f'{channel_name}\n'
    )

    manifest = detect_manifest_type(stream_url)

    if manifest:
        playlist.write(
            "#KODIPROP:inputstream=inputstream.adaptive\n"
        )

        playlist.write(
            f"#KODIPROP:inputstream.adaptive.manifest_type={manifest}\n"
        )

    #
    # DRM Key (KID:KEY)
    #
    if api_key and ":" in api_key:

        playlist.write(
            "#KODIPROP:inputstream.adaptive.license_type=com.widevine.alpha\n"
        )

        playlist.write(
            f"#KODIPROP:inputstream.adaptive.license_key={api_key}\n"
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
        timeout=60
    )

    response.raise_for_status()

    providers = response.json()

    provider_count = 0
    channel_count = 0
    drm_count = 0

    with open(M3U_FILE, "w", encoding="utf-8") as playlist:

        playlist.write("#EXTM3U\n\n")

        for provider in providers:

            provider_count += 1

            provider_name = provider.get(
                "title",
                "Unknown"
            )

            logo = provider.get(
                "image",
                ""
            ).replace("&amp;", "&")

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

                api_key = item.get(
                    "api",
                    ""
                ).strip()

                if not title or not link:
                    continue

                link = link.replace("&amp;", "&")

                stream_url, stream_headers = (
                    parse_url_and_headers(link)
                )

                if api_key and ":" in api_key:
                    drm_count += 1

                write_channel(
                    playlist=playlist,
                    provider_name=provider_name,
                    logo=logo,
                    channel_name=title,
                    stream_url=stream_url,
                    headers=stream_headers,
                    api_key=api_key
                )

                channel_count += 1

    log(f"Providers processed : {provider_count}")
    log(f"Channels written    : {channel_count}")
    log(f"DRM channels found  : {drm_count}")
    log(f"Playlist saved      : {M3U_FILE}")
    log("Finished successfully")


if __name__ == "__main__":
    try:
        main()

    except Exception as e:
        log(f"ERROR: {e}")
        raise

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

JSON_URL = "https://raw.githubusercontent.com/darkbyteprojects/iptv_png/main/provider_6/sports_channels.json"

M3U_FILE = "stv.m3u"
LOG_FILE = "stv.log"

MAX_WORKERS = 50
STREAM_TIMEOUT = 8
CHECK_STREAMS = True

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/151.0.0.0 Safari/537.36"
)

session = requests.Session()
session.headers.update(HEADERS)


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

    header_part = (
        header_part
        .replace("&amp;amp;amp;", "&amp;")
        .replace("&amp;amp;", "&amp;")
        .replace("&amp;", "&")
    )

    headers = {}

    for item in header_part.split("&"):
        if "=" in item:
            k, v = item.split("=", 1)
            headers[k.strip()] = v.strip()

    return stream_url.strip(), headers


def check_stream(url):
    try:

        r = session.get(
            url,
            headers={
                "User-Agent": DEFAULT_UA,
                "Range": "bytes=0-0"
            },
            stream=True,
            allow_redirects=True,
            timeout=STREAM_TIMEOUT
        )

        status = r.status_code
        r.close()

        return status in (200, 206)

    except Exception:
        return False


def validate_channel(channel):

    alive = check_stream(
        channel["stream_url"]
    )

    channel["alive"] = alive

    return channel


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

    manifest = detect_manifest_type(
        stream_url
    )

    if manifest:

        playlist.write(
            "#KODIPROP:inputstream=inputstream.adaptive\n"
        )

        playlist.write(
            f"#KODIPROP:inputstream.adaptive.manifest_type={manifest}\n"
        )

    if api_key and ":" in api_key:

        playlist.write(
            "#KODIPROP:inputstream.adaptive.license_type=clearkey\n"
        )

        playlist.write(
            f"#KODIPROP:inputstream.adaptive.license_key={api_key}\n"
        )

    ua = (
        headers.get("User-Agent")
        or headers.get("user-agent")
        or DEFAULT_UA
    )

    ref = (
        headers.get("Referer")
        or headers.get("referer")
    )

    org = (
        headers.get("Origin")
        or headers.get("origin")
    )

    playlist.write(
        f"#KODIPROP:http-user-agent={ua}\n"
    )

    if ref:

        playlist.write(
            f"#KODIPROP:http-referrer={ref}\n"
        )

    if org:

        playlist.write(
            f"#KODIPROP:http-origin={org}\n"
        )

    playlist.write(
        stream_url + "\n\n"
    )


def main():

    open(LOG_FILE, "w").close()

    log("Starting scrape")

    response = session.get(
        JSON_URL,
        timeout=60
    )

    response.raise_for_status()

    providers = response.json()

    provider_count = 0
    channel_count = 0
    drm_count = 0
    dead_count = 0

    all_channels = []
    seen_urls = set()

    #
    # Collect channels
    #
    for provider in providers:

        provider_count += 1

        provider_name = provider.get(
            "title",
            "Unknown"
        )

        logo = (
            provider.get("image", "")
            .replace("&amp;amp;amp;", "&amp;")
            .replace("&amp;amp;", "&amp;")
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

            api_key = item.get(
                "api",
                ""
            ).strip()

            if not title or not link:
                continue

            link = (
                link
                .replace("&amp;amp;amp;", "&amp;")
                .replace("&amp;amp;", "&amp;")
            )

            stream_url, stream_headers = (
                parse_url_and_headers(link)
            )

            #
            # Skip duplicate URLs
            #
            if stream_url in seen_urls:
                continue

            seen_urls.add(stream_url)

            all_channels.append({
                "provider_name": provider_name,
                "logo": logo,
                "title": title,
                "stream_url": stream_url,
                "headers": stream_headers,
                "api_key": api_key
            })

    log(
        f"Checking {len(all_channels)} streams "
        f"using {MAX_WORKERS} threads..."
    )

    validated_channels = []

    if CHECK_STREAMS:

        with ThreadPoolExecutor(
            max_workers=MAX_WORKERS
        ) as executor:

            futures = [
                executor.submit(
                    validate_channel,
                    channel
                )
                for channel in all_channels
            ]

            total = len(futures)

            for idx, future in enumerate(
                as_completed(futures),
                start=1
            ):

                try:

                    channel = future.result()

                    if channel["alive"]:

                        validated_channels.append(
                            channel
                        )

                        log(
                            f"[{idx}/{total}] OK   "
                            f"{channel['title']}"
                        )

                    else:

                        dead_count += 1

                        log(
                            f"[{idx}/{total}] DEAD "
                            f"{channel['title']}"
                        )

                except Exception as e:

                    dead_count += 1

                    log(
                        f"[{idx}/{total}] ERROR "
                        f"{e}"
                    )

    else:

        validated_channels = all_channels

    with open(
        M3U_FILE,
        "w",
        encoding="utf-8"
    ) as playlist:

        playlist.write("#EXTM3U\n\n")

        for item in validated_channels:

            if (
                item["api_key"]
                and ":" in item["api_key"]
            ):
                drm_count += 1

            write_channel(
                playlist=playlist,
                provider_name=item["provider_name"],
                logo=item["logo"],
                channel_name=item["title"],
                stream_url=item["stream_url"],
                headers=item["headers"],
                api_key=item["api_key"]
            )

            channel_count += 1

    log(f"Providers processed : {provider_count}")
    log(f"Channels checked    : {len(all_channels)}")
    log(f"Channels written    : {channel_count}")
    log(f"Dead channels       : {dead_count}")
    log(f"DRM channels found  : {drm_count}")
    log(f"Playlist saved      : {M3U_FILE}")
    log("Finished successfully")


if __name__ == "__main__":

    try:

        main()

    except Exception as e:

        log(f"ERROR: {e}")
        raise

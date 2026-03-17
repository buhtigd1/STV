
import httpx
import json
import re
import asyncio
import datetime
import xml.etree.ElementTree as ET
from xml.dom import minidom
import os

# ────────────────────────────────────────────────
# Configuration
# ────────────────────────────────────────────────
GITHUB_USERNAME = "buhtigd1"
REPO_NAME = "STV"

DEFAULT_LOGO = ""
EPG_FILENAME = "epg.xml"
M3U_FILENAME = "stv.m3u8"
STREAMS_JSON = "streams.json"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CATEGORY_MAP = {
    15: {"key": 15, "name": "F1"},
    9: {"key": 9, "name": "Football"},
}

NFL_PATTERNS = ["NFL", "NATIONAL FOOTBALL"]


# ────────────────────────────────────────────────
# Resolve .php → .m3u8
# ────────────────────────────────────────────────
async def resolve_m3u8(client: httpx.AsyncClient, embed_url: str) -> str:

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://streams.center/",
    }

    try:
        r1 = await client.get(embed_url, headers=headers, follow_redirects=True)

        iframe_match = re.search(
            r'<iframe\s+src="\'["\']',
            r1.text,
            re.I
        )

        if not iframe_match:
            return embed_url

        inner = iframe_match.group(1)
        if inner.startswith("//"):
            inner = "https:" + inner

        headers["Referer"] = embed_url
        r2 = await client.get(inner, headers=headers, follow_redirects=True)

        input_match = re.search(
            r'input\s*:\s*"\'["\']',
            r2.text
        )

        if input_match:
            decrypt = await client.post(
                "https://streams.center/embed/decrypt.php",
                data={"input": input_match.group(1)},
                headers={
                    **headers,
                    "X-Requested-With": "XMLHttpRequest",
                    "Referer": inner,
                },
            )

            if decrypt.is_success and ".m3u8" in decrypt.text:
                return decrypt.text.strip()

        return embed_url

    except Exception:
        return embed_url


# ────────────────────────────────────────────────
# Main Scraper
# ────────────────────────────────────────────────
async def main():
    api_url = "https://backend.streamcenter.live/api/Parties?pageNumber=1&pageSize=500"
    epg_url = f"https://raw.githubusercontent.com/{GITHUB_USERNAME}/{REPO_NAME}/main/epg.xml"

    async with httpx.AsyncClient(timeout=35.0, verify=False) as client:

        resp = await client.get(api_url)
        resp.raise_for_status()
        games = resp.json()

        raw_streams = []

        for game in games:
            vid_str = game.get("videoUrl", "").strip()
            if not vid_str:
                continue

            gid = str(game.get("id"))
            name = game.get("gameName") or game.get("name", "No name")
            start = game.get("beginPartie")
            cid = game.get("categoryId")

            logo1 = game.get("logoTeam1")
            logo2 = game.get("logoTeam2")

            for chunk in vid_str.split(";"):
                chunk = chunk.strip()
                if not chunk:
                    continue
                                 
                if "<" in chunk:
                    url, lang = [x.strip() for x in chunk.split("<", 1)]
                    lang = lang.rstrip(">")
                else:
                    url, lang = chunk, "English"
               
        # ────────────────────────────────────────────────
        # M3U — ONLY FOOTBALL & F1
        # ────────────────────────────────────────────────
        with open(os.path.join(BASE_DIR, M3U_FILENAME), "w", encoding="utf-8") as f:
            f.write(f'#EXTM3U x-tvg-url="{epg_url}"\n')

            for s in valid:
                category = "F1" if s["categoryId"] == 15 else "Football"
                logo = s.get("logoTeam1") or s.get("logoTeam2") or DEFAULT_LOGO

                f.write(
                    f'#EXTINF:-1 tvg-id="{s["id"]}" '
                    f'tvg-logo="{logo}" group-title="{category}",{s["name"]}\n'
                )
                f.write('#EXTVLCOPT:http-user-agent=Mozilla/5.0\n')
                f.write('#EXTVLCOPT:http-referrer=https://streams.center/\n')
                f.write(f'{s["url"]}\n')

        with open(os.path.join(BASE_DIR, STREAMS_JSON), "w", encoding="utf-8") as f:
            json.dump(valid, f, indent=2, ensure_ascii=False)

        print("Done.")


# ────────────────────────────────────────────────
if __name__ == "__main__":
    asyncio.run(main())

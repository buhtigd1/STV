
import httpx
import json
import re
import asyncio
import datetime
import xml.etree.ElementTree as ET
from xml.dom import minidom
import os

GITHUB_USERNAME = "buhtigd1"
REPO_NAME = "STV"

DEFAULT_LOGO = ""
EPG_FILENAME = "epg.xml"
M3U_FILENAME = "stv.m3u8"
STREAMS_JSON = "streams.json"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

async def resolve_m3u8(client, embed_url):
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://streams.center/"}
    try:
        r1 = await client.get(embed_url, headers=headers, follow_redirects=True)
        iframe_match = re.search(r'<iframe\s+src="\'["\']', r1.text, re.I)
        if not iframe_match:
            return embed_url

        inner = iframe_match.group(1)
        if inner.startswith("//"):
            inner = "https:" + inner

        headers["Referer"] = embed_url
        r2 = await client.get(inner, headers=headers, follow_redirects=True)

        input_match = re.search(r'input\s*:\s*"\'["\']', r2.text)
        if input_match:
            decrypt = await client.post(
                "https://streams.center/embed/decrypt.php",
                data={"input": input_match.group(1)},
                headers={"User-Agent": "Mozilla/5.0", "Referer": inner, "X-Requested-With": "XMLHttpRequest"}
            )
            if decrypt.is_success and ".m3u8" in decrypt.text:
                return decrypt.text.strip()

        return embed_url
    except:
        return embed_url


async def main():
    api_url = "https://backend.streamcenter.live/api/Parties?pageNumber=1&pageSize=500"
    epg_url = f"https://raw.githubusercontent.com/{GITHUB_USERNAME}/{REPO_NAME}/main/epg.xml"

    async with httpx.AsyncClient(timeout=35.0, verify=False) as client:

        resp = await client.get(api_url)
        resp.raise_for_status()
        games = resp.json()

        raw_streams = []

        for game in games:
            vid_str = game.get("videoUrl", "")
            if not vid_str:
                continue

            gid = str(game.get("id"))
            name = game.get("gameName") or game.get("name") or "No name"
            cid = game.get("categoryId")
            start = game.get("beginPartie")
            logo1 = game.get("logoTeam1")
            logo2 = game.get("logoTeam2")

            for chunk in vid_str.split(";"):
                chunk = chunk.strip()
                if not chunk:
                    continue

                if "<" in chunk:
                    parts = chunk.split("<", 1)
                    url = parts[0].""
                f.write(f'#EXTINF:-1 tvg-id="{s["id"]}" tvg-logo="{logo}" group-title="{group}",{s["name"]}\n')
                f.write('https://streams.center/\n')
                f.write(f'{s["url"]}\n')

        with open(os.path.join(BASE_DIR, STREAMS_JSON), "w", encoding="utf-8") as f:
            json.dump(valid, f, indent=2)

        print("Done")


if __name__ == "__main__":
    asyncio.run(main())

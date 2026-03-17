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

        iframe_match = re.search(r'\")
                else:
                    url = chunk
                    lang = "English"

                if url.startswith("http"):
                    raw_streams.append({
                        "id": gid,
                        "name": f"{name} ({lang})",
                        "url": url,
                        "categoryId": cid,
                        "start": start,
                        "logo1": logo1,
                        "logo2": logo2,
                    })

        semaphore = asyncio.Semaphore(4)

        async def process(s):
            async with semaphore:
                if ".php" in s["url"]:
                    s["url"] = await resolve_m3u8(client, s["url"])
                return s

        resolved = await asyncio.gather(*(process(s) for s in raw_streams))

        valid = [r for r in resolved if isinstance(r, dict) and ".m3u8" in r["url"]]
        valid = [v for v in valid if v["categoryId"] in [9, 15]]

        root = ET.Element("tv")

        for s in valid:
            ch = ET.SubElement(root, "channel", id=s["id"])
            ET.SubElement(ch, "display-name").text = s["name"]

            now = datetime.datetime.utcnow()
            st = now.strftime("%Y%m%d%H%M%S +0000")
            en = (now + datetime.timedelta(hours=6)).strftime("%Y%m%d%H%M%S +0000")

            prog = ET.SubElement(root, "programme", start=st, stop=en, channel=s["id"])
            ET.SubElement(prog, "title", lang="en").text = s["name"]

        with open(os.path.join(BASE_DIR, EPG_FILENAME), "w", encoding="utf-8") as f:
            f.write(minidom.parseString(ET.tostring(root)).toprettyxml(indent="  "))

        with open(os.path.join(BASE_DIR, M3U_FILENAME), "w", encoding="utf-8") as f:
            f.write(f'#EXTM3U x-tvg-url="{epg_url}"\n')
            for s in valid:
                group = "F1" if s["categoryId"] == 15 else "Football"
                logo = s["logo1"] or s["logo2"] or ""
                f.write(
                    f'#EXTINF:-1 tvg-id="{s["id"]}" tvg-logo="{logo}" group-title="{group}",{s["name"]}\n'
                )
                f.write(f"{s['url']}\n")

        with open(os.path.join(BASE_DIR, STREAMS_JSON), "w", encoding="utf-8") as f:
            json.dump(valid, f, indent=2)

        print("Done")


if __name__ == "__main__":
    asyncio.run(main())

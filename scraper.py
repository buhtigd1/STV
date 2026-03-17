
import httpx
import json
import re
import asyncio
import datetime
import xml.etree.ElementTree as ET
from xml.dom import minidom
import os
from collections import defaultdict

# ────────────────────────────────────────────────
# Configuration
# ────────────────────────────────────────────────
GITHUB_USERNAME = "buhtigd1"
REPO_NAME       = "STV"

DEFAULT_LOGO = ""
EPG_FILENAME    = "epg.xml"
M3U_FILENAME    = "stv.m3u8"
STREAMS_JSON    = "streams.json"
CATEGORIES_JSON = "categories.json"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Category mapping
CATEGORY_MAP = {
    15:  {"key": 15,  "name": "F1",       "icon": "🏎️", "priority": 0},
    9:   {"key": 9,   "name": "Football", "icon": "⚽", "priority": 1},
    "other": {"key": "other", "name": "Other", "icon": "", "priority": 99},
}

NFL_PATTERNS = ["NFL", "NATIONAL FOOTBALL"]

# ────────────────────────────────────────────────
async def resolve_m3u8(client: httpx.AsyncClient, embed_url: str) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://streams.center/",
    }
    try:
        r1 = await client.get(embed_url, headers=headers, follow_redirects=True)
        iframe_match = re.search(r'<iframe\s+src["\']([^"\ r1.text, re.I)
        if not iframe_match:
            return embed_url

        inner = iframe_match.group(1)
        if inner.startswith("//"):
            inner = "https:" + inner

        headers["Referer"] = embed_url
        r2 = await client.get(inner, headers=headers, follow_redirects=True)

        input_match = re.search(r'input\s*:\s*["\']([A-Za-z0-9+/)
        if input_match:
            decrypt = await client.post(
                "https://streams.center/embed/decrypt.php",
                data={"input": input_match.group(1)},
                headers={
                    **headers,
                    "X-Requested-With": "XMLHttpRequest",
                    "Referer": inner
                }
            )
            if decrypt.is_success and ".m3u8" in decrypt.text:
                return decrypt.text.strip()

        return embed_url

    except Exception as e:
        print(f"Resolve failed: {embed_url} → {e}")
        return embed_url


async def main():
    api_url = "https://backend.streamcenter.live/api/Parties?pageNumber=1&pageSize=500"
    epg_url = f"https://raw.githubusercontent.com/{GITHUB_USERNAME}/{REPO_NAME}/main/epg.xml"

    async with httpx.AsyncClient(timeout=httpx.Timeout(35.0), verify=False) as client:
        try:
            print("Fetching events...")
            resp = await client.get(api_url)
            resp.raise_for_status()
            games = resp.json()
            print(f"→ {len(games)} events received")

            raw_streams = []
            for game in games:
                vid_str = game.get("videoUrl", "").strip()
                if not vid_str:
                    continue

                gid = str(game.get("id", "unknown"))
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

                    if url.startswith("http"):
                        raw_streams.append({
                            "id": gid,
                            "name": f"{name} ({lang})",
                            "url": url,
                            "categoryId": cid,
                            "start": start,
                            "original_name_upper": name.upper(),
                            "logoTeam1": logo1,
                            "logoTeam2": logo2
                        })

            # Resolve .php links into .m3u8
            semaphore = asyncio.SEMAPHORE = (4)
            async def process(s):
                async with asyncio.Semaphore(4):
                    if ".php" in s["url"]:
                        s["url"] = await resolve_m3u8(client, s["url"])
                    return s

            print(f"Resolving {len(raw_streams)} links...")
            resolved = await asyncio.gather(*(process(s) for s in raw_streams))

            valid = [r for r in resolved if isinstance(r, dict) and ".m3u8" in r.get("url", "")]
            valid.sort(key=lambda x: x.get("start") or "9999")

            # ──────────────── FILTER ONLY FOOTBALL & F1 ────────────────
            valid = [v for v in valid if v.get("categoryId") in [9, 15]]

            # EPG generation
            root = ET.Element("tv")
            for s in valid:
                ch = ET.SubElement(root, "channel", id=s["id"])
                ET.SubElement(ch, "display-name").text = s["name"]
                ET.SubElement(ch, "icon", src=DEFAULT_LOGO)

                now = datetime.datetime.now(datetime.timezone.utc)
                st = now.strftime("%Y%m%d%H%M%S +0000")
                en = (now + datetime.timedelta(hours=6)).strftime("%Y%m%d%H%M%S +0000")

                prog = ET.SubElement(root, "programme", start=st, stop=en, channel=s["id"])
                ET.SubElement(prog, "title", lang="en").text = s["name"]
                ET.SubElement(prog, "icon", src=DEFAULT_LOGO)

            with open(os.path.join(BASE_DIR, EPG_FILENAME), "w", encoding="utf-8") as f:
                f.write(minidom.parseString(ET.tostring(root)).toprettyxml(indent="  "))

            # ───────────── M3U (ONLY FOOTBALL & F1) ─────────────
            with open(os.path.join(BASE_DIR, M3U_FILENAME), "w", encoding="utf-8") as f:
                f.write(f'#EXTM3U x-tvg-url="{epg_url}"\n')

                for s in valid:
                    cid = s.get("categoryId")
                    group_name = "F1" if cid == 15 else "Football"

                    # Select best logo
                    logo = s.get("logoTeam1") or s.get("logoTeam2") or DEFAULT_LOGO

                    f.write(
                        f'#EXTINF:-1 tvg-id="{s["id"]}" '
                        f'tvg-logo="{logo}" group-title="{group_name}",{s["name"]}\n'
                    )
                    f.write('#EXTVLCOPT:http-user-agent=Mozilla/5.0 (Windows NT 10.0)\n')
                    f.write('#EXTVLCOPT:http-referrer=https://streams.center/\n')
                    f.write(f'{s["url"]}\n')

            # Save JSON
            with open(os.path.join(BASE_DIR, STREAMS_JSON), "w", encoding="utf-8") as f:
                json.dump(valid, f, indent=2, ensure_ascii=False)

            print("Done.")

        except Exception as e:
            print(f"Error: {type(e).__name__}: {e}")


if __name__ == "__main__":
    asyncio.run(main())

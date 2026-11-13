"""
해커톤 챌린지 페이지의 Resources 탭을 읽어 자료 링크를 뽑는다(원격에서도 명령 한 줄).

    python -m hackathon.challenge_watch                 # 지금 내용과 링크, 지난번과 달라진 점
    python -m hackathon.challenge_watch --download      # 자료로 보이는 링크를 fetch로 받기 (../data/hackathon_2026)

- 페이지는 화면이 뜬 뒤 Space Apps GraphQL API에서 탭 내용을 불러온다. 같은 질의(pageByPath →
  ChallengePage.resourcesTabContent)를 Origin 헤더와 함께 보낸다.
- 결과는 ../outputs/hackathon/challenge/ 에 시각별로 저장하고, 마지막 내용과 비교해 새 링크를 알려 준다.
- 2026-11-13 확인 시 탭 내용: "Resources will be available on Friday, November 13."
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import re
import urllib.request

API = "https://api.spaceappschallenge.org/graphql"
SITE = "https://www.spaceappschallenge.org"
PATH = "/2026/challenges/interplanetary-survival-guide-martian-map/"
OUT = "../outputs/hackathon/challenge"
QUERY = "query($p:String!){ pageByPath(path:$p){ __typename id ... on ChallengePage { title excerpt detailsContent resourcesTabContent } } }"
DATA_EXT = (".zip", ".tar", ".gz", ".tgz", ".csv", ".tsv", ".json", ".geojson", ".tif", ".tiff", ".img", ".lbl", ".jp2",
            ".png", ".jpg", ".nc", ".h5", ".hdf", ".xlsx", ".txt", ".kml", ".shp", ".las", ".laz", ".npy", ".pds")
DATA_HOSTS = ("pds", "earthdata", "trek.nasa.gov", "mars.nasa.gov", "astrogeology.usgs.gov", "planetarymaps", "github.com",
              "drive.google.com", "data.nasa.gov", "hirise", "ode.rsl.wustl.edu", "zenodo", "figshare", "s3.amazonaws.com")


def fetch_page(path=PATH):
    body = json.dumps({"query": QUERY, "variables": {"p": path}}).encode()
    req = urllib.request.Request(API, data=body, headers={"Content-Type": "application/json", "Origin": SITE,
                                                         "Referer": SITE + path, "User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.load(r)
    if d.get("errors"):
        raise SystemExit(f"API 오류: {d['errors'][0].get('message')}")
    return d["data"]["pageByPath"]


def links_of(html_text):
    out = []
    for m in re.finditer(r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', html_text or "", re.S):
        url, label = html.unescape(m.group(1)), re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", m.group(2)))).strip()
        if url.startswith("/"):
            url = SITE + url
        low = url.lower().split("?")[0]
        kind = "data" if low.endswith(DATA_EXT) or any(h in low for h in DATA_HOSTS) else "page"
        out.append({"url": url, "label": label, "kind": kind})
    return out


def text_of(html_text):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", html_text or ""))).strip()


def main(args):
    os.makedirs(OUT, exist_ok=True)
    pg = fetch_page(args.path)
    res = pg.get("resourcesTabContent") or ""
    links = links_of(res)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M")
    snap = {"time": stamp, "title": pg.get("title"), "resources_text": text_of(res), "links": links}
    last_p = f"{OUT}/latest.json"
    old = json.load(open(last_p, encoding="utf-8")) if os.path.exists(last_p) else {"links": [], "resources_text": ""}
    new_links = [l for l in links if l["url"] not in {o["url"] for o in old["links"]}]
    json.dump(snap, open(f"{OUT}/resources_{stamp}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(snap, open(last_p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    open(f"{OUT}/details.txt", "w", encoding="utf-8").write(text_of(pg.get("detailsContent")))
    print(f"[{stamp}] {snap['title']}")
    print(f"Resources 탭: {snap['resources_text'][:400]}")
    print(f"링크 {len(links)}개 (자료로 보이는 것 {sum(l['kind'] == 'data' for l in links)}개), 지난번 대비 새 링크 {len(new_links)}개")
    for l in links:
        print(f"  {'★' if l in new_links else ' '} [{l['kind']}] {l['label'][:60]} — {l['url']}")
    if old["resources_text"] and old["resources_text"] != snap["resources_text"] and not new_links:
        print("  (링크는 같지만 탭 글이 바뀌었습니다)")
    if args.download:
        from hackathon import fetch
        urls = [l["url"] for l in links if l["kind"] == "data"]
        if not urls:
            print("받을 자료 링크가 없습니다.")
        else:
            fetch.main(urls, args.to, extract=True, run_intake=True)
    return snap, new_links


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--path", default=PATH)
    ap.add_argument("--download", action="store_true")
    ap.add_argument("--to", default="../data/hackathon_2026")
    main(ap.parse_args())

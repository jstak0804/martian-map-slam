"""
원격 Claude Code에서 해커톤 자료를 받는 도구. 링크만 주면 받아서 풀고 접수(intake)까지 한다.

    python -m hackathon.fetch <링크> [<링크> ...] [--to ../data/hackathon_2026] [--no-extract] [--no-intake]
    python -m hackathon.fetch --list <폴더 목록 페이지 링크> [--pattern '\\.(IMG|JP2)$']   # 목록만 보기
    python -m hackathon.fetch --crawl <폴더 목록 페이지 링크> --pattern '\\.csv$'          # 목록에서 골라 받기

알아서 처리하는 링크:
  - 일반 파일 (http/https): 이어받기(Range), 진행 표시, SHA-256 기록
  - Google Drive 공유 링크 (drive.google.com/file/d/<id>/...): 큰 파일 확인 단계까지. 폴더 링크는 Drive 커넥터로(REMOTE.md)
  - Dropbox 공유 링크 (?dl=0 -> dl=1), GitHub blob 링크 -> raw
  - GitHub 릴리스 (github.com/<o>/<r>/releases/tag/<t> 또는 /releases/latest): 첨부 파일 전부
  - 폴더 목록 페이지(PDS 같은 Apache 목록): --list / --crawl
  - NASA Earthdata: 환경변수 EARTHDATA_TOKEN이 있으면 Bearer 토큰으로 (토큰은 채팅에 쓰지 말고 ~/.bashrc에)
받은 기록: <받는 폴더>/sources.json (링크, 파일, 크기, SHA-256, 시각)
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
import tarfile
import urllib.parse
import urllib.request
import zipfile
from http.cookiejar import CookieJar

UA = "Mozilla/5.0 (martian-map-slam fetch)"
EARTHDATA_HOSTS = ("earthdata.nasa.gov", "urs.earthdata.nasa.gov", "cmr.earthdata.nasa.gov", "e4ftl01.cr.usgs.gov",
                   "daac", "asf.alaska.edu", "pds-imaging.jpl.nasa.gov")
_jar = CookieJar()
_opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(_jar))


def _req(url, extra=None):
    h = {"User-Agent": UA}
    tok = os.environ.get("EARTHDATA_TOKEN")
    if tok and any(x in url for x in EARTHDATA_HOSTS):
        h["Authorization"] = f"Bearer {tok}"
    h.update(extra or {})
    return urllib.request.Request(url, headers=h)


def normalize(url):
    """공유 링크를 바로 받을 수 있는 링크로."""
    m = re.search(r"drive\.google\.com/(?:file/d/|open\?id=|uc\?(?:.*&)?id=)([\w-]+)", url)
    if m:
        return f"https://drive.google.com/uc?export=download&id={m.group(1)}", "gdrive"
    if "drive.google.com/drive/folders" in url:
        raise SystemExit("Google Drive 폴더 링크는 여기서 못 받습니다. 폴더 안 파일 링크를 주시거나 Drive 커넥터로 받습니다(REMOTE.md).")
    if "dropbox.com" in url:
        return re.sub(r"([?&])dl=0", r"\1dl=1", url if "dl=" in url else url + ("&" if "?" in url else "?") + "dl=1"), "dropbox"
    m = re.match(r"https://github\.com/([^/]+)/([^/]+)/blob/(.+)", url)
    if m:
        return f"https://raw.githubusercontent.com/{m.group(1)}/{m.group(2)}/{m.group(3)}", "github"
    return url, "http"


def github_release_assets(url):
    m = re.match(r"https://github\.com/([^/]+)/([^/]+)/releases/(?:tag/(.+)|latest)", url)
    if not m:
        return None
    o, r, tag = m.groups()
    api = f"https://api.github.com/repos/{o}/{r}/releases/" + (f"tags/{tag}" if tag else "latest")
    with _opener.open(_req(api, {"Accept": "application/vnd.github+json"}), timeout=30) as f:
        rel = json.load(f)
    return [a["browser_download_url"] for a in rel.get("assets", [])]


def list_index(url, pattern=None):
    """Apache/PDS 같은 폴더 목록 페이지에서 파일 링크를 뽑는다."""
    with _opener.open(_req(url), timeout=60) as f:
        page = f.read().decode("utf-8", "replace")
    out = []
    for href in re.findall(r'href="([^"?#]+)"', page):
        if href.startswith(("../", "/")) and not href.startswith(urllib.parse.urlparse(url).path):
            continue
        full = urllib.parse.urljoin(url, href)
        if full.rstrip("/") == url.rstrip("/") or full.endswith("/"):
            continue
        if pattern and not re.search(pattern, full, re.I):
            continue
        out.append(full)
    return sorted(dict.fromkeys(out))


def _name_from(resp, url):
    cd = resp.headers.get("Content-Disposition", "")
    m = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)', cd)
    if m:
        return urllib.parse.unquote(m.group(1))
    return urllib.parse.unquote(os.path.basename(urllib.parse.urlparse(resp.geturl() or url).path)) or "download.bin"


def download(url, to_dir):
    u, kind = normalize(url)
    os.makedirs(to_dir, exist_ok=True)
    resp = _opener.open(_req(u), timeout=60)
    if kind == "gdrive" and "text/html" in resp.headers.get("Content-Type", ""):     # 큰 파일: 바이러스 검사 확인 단계
        page = resp.read().decode("utf-8", "replace")
        form = re.search(r'action="([^"]+)"', page)
        params = dict(re.findall(r'name="(\w+)" value="([^"]*)"', page))
        if not form:
            raise SystemExit("Google Drive가 파일을 주지 않습니다. 공유 설정을 '링크가 있는 모든 사용자'로 바꿔 주세요.")
        resp = _opener.open(_req(form.group(1) + "?" + urllib.parse.urlencode(params)), timeout=60)
    name = _name_from(resp, u)
    path = os.path.join(to_dir, name)
    total = int(resp.headers.get("Content-Length") or 0)
    have = os.path.getsize(path) if os.path.exists(path) else 0
    if total and have == total:
        print(f"  이미 있음: {name} ({total / 1e6:.1f} MB)"); resp.close()
    else:
        mode = "wb"
        if have and resp.headers.get("Accept-Ranges") == "bytes" and total:
            resp.close()
            resp = _opener.open(_req(u, {"Range": f"bytes={have}-"}), timeout=60)
            mode = "ab"
        done = have if mode == "ab" else 0
        with open(path, mode) as f:
            while True:
                chunk = resp.read(1 << 20)
                if not chunk:
                    break
                f.write(chunk); done += len(chunk)
                if total:
                    sys.stdout.write(f"\r  {name}: {done / 1e6:.1f}/{total / 1e6:.1f} MB"); sys.stdout.flush()
        print(f"\r  받음: {name} ({done / 1e6:.1f} MB)" + " " * 20)
    sha = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            sha.update(chunk)
    return {"url": url, "file": name, "bytes": os.path.getsize(path), "sha256": sha.hexdigest(),
            "time": dt.datetime.now().isoformat(timespec="seconds")}


def extract(path, to_dir):
    stem = os.path.splitext(os.path.basename(path))[0].replace(".tar", "")
    dest = os.path.join(to_dir, stem)
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as z:
            for m in z.namelist():                   # 경로 밖으로 나가는 항목은 거부
                if os.path.isabs(m) or ".." in m.split("/"):
                    raise SystemExit(f"압축 안에 위험한 경로가 있습니다: {m}")
            z.extractall(dest)
        return dest
    if tarfile.is_tarfile(path):
        with tarfile.open(path) as t:
            for m in t.getmembers():
                if os.path.isabs(m.name) or ".." in m.name.split("/") or m.issym() or m.islnk():
                    raise SystemExit(f"압축 안에 위험한 항목이 있습니다: {m.name}")
            t.extractall(dest)
        return dest
    return None


def main(urls, to_dir, extract=True, run_intake=True, name="hackathon_2026"):
    expanded = []
    for u in urls:
        assets = github_release_assets(u) if "github.com" in u and "/releases" in u else None
        expanded.extend(assets if assets is not None else [u])
    log_p = os.path.join(to_dir, "sources.json")
    os.makedirs(to_dir, exist_ok=True)
    log = json.load(open(log_p, encoding="utf-8")) if os.path.exists(log_p) else []
    for u in expanded:
        try:
            rec = download(u, to_dir)
        except SystemExit as e:
            print(f"  실패: {u}\n    {e}"); continue
        except Exception as e:
            print(f"  실패: {u}\n    {type(e).__name__}: {e}"); continue
        if extract:
            d = globals()["extract"](os.path.join(to_dir, rec["file"]), to_dir)
            if d:
                rec["extracted_to"] = os.path.relpath(d, to_dir); print(f"  풀기: {rec['extracted_to']}/")
        log = [r for r in log if r["file"] != rec["file"]] + [rec]
        json.dump(log, open(log_p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if run_intake:
        from hackathon import intake
        intake.main(to_dir, name)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("urls", nargs="*")
    ap.add_argument("--to", default="../data/hackathon_2026")
    ap.add_argument("--name", default="hackathon_2026")
    ap.add_argument("--list", metavar="INDEX_URL")
    ap.add_argument("--crawl", metavar="INDEX_URL")
    ap.add_argument("--pattern")
    ap.add_argument("--no-extract", action="store_true")
    ap.add_argument("--no-intake", action="store_true")
    a = ap.parse_args()
    if a.list:
        for u in list_index(a.list, a.pattern):
            print(u)
    else:
        urls = list(a.urls) + (list_index(a.crawl, a.pattern) if a.crawl else [])
        if not urls:
            ap.error("받을 링크가 없습니다")
        main(urls, a.to, not a.no_extract, not a.no_intake, a.name)

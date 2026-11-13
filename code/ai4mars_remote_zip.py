"""
원격 ZIP 부분 다운로드 — AI4Mars 전체 데이터셋(16GB, Zenodo)에서 필요한 파일만 뽑기

공식 AI4Mars 데이터셋은 Zenodo에 16GB 짜리 zip 하나로만 공개되어 있다(merged-0.6.zip,
146,179개 항목). 전체를 받을 필요 없이, HTTP Range 요청으로 ZIP 중앙 디렉터리(약 26MB)만
먼저 받아 각 파일의 바이트 오프셋을 알아낸 뒤, 학습에 쓸 이미지·마스크 수백 장만 개별
Range 요청으로 뽑아낸다 — Devon Island FTP에서 썼던 것과 같은 부분 다운로드 전략을
ZIP 포맷 레벨에서 직접 구현한 것 (ZIP64 포맷 — 항목 14만개+/16GB라 32비트 필드로는
표현이 안 되어 ZIP64 central directory locator/record를 거쳐야 한다).
"""
from __future__ import annotations

import http.client
import socket
import struct
import time
import urllib.request
import urllib.error
import zlib

ZENODO_RECORD = "15995036"
ZIP_URL = f"https://zenodo.org/api/records/{ZENODO_RECORD}/files/ai4mars-dataset-merged-0.6.zip/content"

EOCD_SIG = b"PK\x05\x06"
ZIP64_LOC_SIG = b"PK\x06\x07"
ZIP64_EOCD_SIG = b"PK\x06\x06"
CD_ENTRY_SIG = b"PK\x01\x02"
LOCAL_HDR_SIG = b"PK\x03\x04"

_MAX_RETRIES = 5


def _fetch_range(lo: int, hi: int) -> bytes:
    """[lo, hi] 양끝 포함 바이트 범위를 가져온다. 429(rate limit)나 끊긴 연결은 재시도."""
    req = urllib.request.Request(ZIP_URL, headers={"Range": f"bytes={lo}-{hi}"})
    for attempt in range(_MAX_RETRIES):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < _MAX_RETRIES - 1:
                wait = 2 ** attempt * 3
                print(f"  rate limited, {wait}s 대기 후 재시도...")
                time.sleep(wait)
                continue
            raise
        except (http.client.IncompleteRead, ConnectionError, socket.timeout,
                 urllib.error.URLError) as e:
            if attempt < _MAX_RETRIES - 1:
                wait = 2 ** attempt
                print(f"  네트워크 오류({e}), {wait}s 대기 후 재시도...")
                time.sleep(wait)
                continue
            raise
    raise RuntimeError("재시도 횟수 초과")


class ZipEntry:
    __slots__ = ("name", "offset", "comp_size", "uncomp_size", "method")

    def __init__(self, name, offset, comp_size, uncomp_size, method):
        self.name, self.offset = name, offset
        self.comp_size, self.uncomp_size, self.method = comp_size, uncomp_size, method


def _get_total_size() -> int:
    req = urllib.request.Request(ZIP_URL, method="HEAD")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return int(resp.headers["Content-Length"])


def load_central_directory(verbose: bool = True) -> dict[str, ZipEntry]:
    """ZIP64 EOCD를 찾아 중앙 디렉터리 전체를 받아 {파일명: ZipEntry} 맵으로 파싱한다.
    전체 요청 수: 2~3번(꼬리 탐색 + zip64 EOCD + 중앙 디렉터리 본문)뿐, 파일 개수와 무관."""
    total_size = _get_total_size()
    if verbose:
        print(f"원격 zip 전체 크기: {total_size / 1e9:.2f} GB")

    tail_size = 65557
    tail = _fetch_range(total_size - tail_size, total_size - 1)

    loc_idx = tail.rfind(ZIP64_LOC_SIG)
    if loc_idx == -1:
        raise RuntimeError("ZIP64 locator를 찾지 못함 — 이 코드는 ZIP64 포맷 전용")
    _, _, zip64_eocd_offset, _ = struct.unpack("<IIQI", tail[loc_idx:loc_idx + 20])

    z64 = _fetch_range(zip64_eocd_offset, zip64_eocd_offset + 1023)
    (_, _, _, _, _, _, _, n_entries, cd_size, cd_offset) = struct.unpack("<IQHHIIQQQQ", z64[:56])
    if verbose:
        print(f"항목 {n_entries}개, 중앙 디렉터리 {cd_size / 1e6:.1f}MB @ offset {cd_offset}")

    cd_bytes = _fetch_range(cd_offset, cd_offset + cd_size - 1)

    entries: dict[str, ZipEntry] = {}
    pos = 0
    for _ in range(n_entries):
        if cd_bytes[pos:pos + 4] != CD_ENTRY_SIG:
            raise RuntimeError(f"중앙 디렉터리 파싱 오류 @ {pos}")
        (_, _, _, _, method, _, _, _, comp_size, uncomp_size,
         name_len, extra_len, comment_len, _, _, _, local_offset) = struct.unpack(
            "<IHHHHHHIIIHHHHHII", cd_bytes[pos:pos + 46]
        )
        pos += 46
        name = cd_bytes[pos:pos + name_len].decode("utf-8", errors="replace")
        pos += name_len
        extra = cd_bytes[pos:pos + extra_len]
        pos += extra_len
        pos += comment_len

        # zip64 필드가 0xFFFFFFFF 센티널이면 extra field(id=0x0001)에서 실제 64비트 값을 읽는다
        if comp_size == 0xFFFFFFFF or uncomp_size == 0xFFFFFFFF or local_offset == 0xFFFFFFFF:
            ep = 0
            while ep + 4 <= len(extra):
                fid, fsize = struct.unpack("<HH", extra[ep:ep + 4])
                if fid == 0x0001:
                    body = extra[ep + 4:ep + 4 + fsize]
                    bp = 0
                    if uncomp_size == 0xFFFFFFFF:
                        uncomp_size = struct.unpack_from("<Q", body, bp)[0]; bp += 8
                    if comp_size == 0xFFFFFFFF:
                        comp_size = struct.unpack_from("<Q", body, bp)[0]; bp += 8
                    if local_offset == 0xFFFFFFFF:
                        local_offset = struct.unpack_from("<Q", body, bp)[0]; bp += 8
                    break
                ep += 4 + fsize

        entries[name] = ZipEntry(name, local_offset, comp_size, uncomp_size, method)

    if verbose:
        print(f"파싱 완료: {len(entries)}개 항목")
    return entries


def extract(entry: ZipEntry) -> bytes:
    """해당 항목의 로컬 헤더+압축 데이터를 '단 한 번'의 Range 요청으로 가져와 압축해제."""
    # 로컬 헤더(최대 30바이트 고정 + 파일명/extra, 넉넉히 512바이트 버퍼) + 압축 데이터
    chunk = _fetch_range(entry.offset, entry.offset + 512 + entry.comp_size - 1)
    if chunk[:4] != LOCAL_HDR_SIG:
        raise RuntimeError(f"로컬 헤더 시그니처 불일치: {entry.name}")
    name_len, extra_len = struct.unpack("<HH", chunk[26:30])
    data_start = 30 + name_len + extra_len
    comp_data = chunk[data_start:data_start + entry.comp_size]
    if len(comp_data) != entry.comp_size:
        # 버퍼가 부족했던 드문 경우(긴 extra 필드) — 정확한 범위로 재요청
        comp_data = _fetch_range(
            entry.offset + data_start, entry.offset + data_start + entry.comp_size - 1
        )
    if entry.method == 0:
        return comp_data
    elif entry.method == 8:
        return zlib.decompress(comp_data, -15)
    raise RuntimeError(f"지원하지 않는 압축 방식 {entry.method}: {entry.name}")

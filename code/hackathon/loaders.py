"""
형식이 정해지지 않은 해커톤 데이터를 읽는 공통 도구.

- read_table(path): CSV/TSV/TXT -> {열 이름: 값 목록}. 숫자는 float, 시간 문자열은 초로 바꾼다.
- detect_roles(header): 열 이름으로 역할(심박, 대사량, 속도, 경사, 선량 ...)과 단위를 추정한다.
- load_dem(path): PDS IMG(+LBL), GeoTIFF(Pillow 또는 rasterio), .npy -> (고도 배열, 화소 크기 m, 정보)
- find_image_mask_pairs(root): 영상과 분할 마스크 쌍을 파일 이름으로 맞춘다.

추정이 틀릴 수 있으므로 intake 보고서에 무엇을 어떻게 읽었는지 그대로 남긴다.
열 역할을 직접 지정하려면 데이터 폴더에 columns.json을 둔다:
    {"eva_physio.csv": {"hr": "HR (bpm)", "mr_w": "Met rate"}}
"""
from __future__ import annotations

import csv
import datetime as dt
import glob
import json
import os
import re

import numpy as np

# ---------------------------------------------------------------- 표 데이터
TIME_RE = re.compile(r"^\d{1,2}:\d{2}(:\d{2}(\.\d+)?)?$")


def _to_seconds(v: str):
    v = v.strip()
    if TIME_RE.match(v):
        parts = [float(x) for x in v.split(":")]
        while len(parts) < 3:
            parts.append(0.0)
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    try:
        return dt.datetime.fromisoformat(v.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def read_table(path: str, max_rows: int | None = None):
    with open(path, newline="", encoding="utf-8-sig", errors="replace") as f:
        sample = f.read(4096)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t ")
        except csv.Error:
            dialect = csv.excel
        rd = csv.reader(f, dialect)
        header = [h.strip() for h in next(rd)]
        cols = {h: [] for h in header}
        for i, row in enumerate(rd):
            if max_rows and i >= max_rows:
                break
            for h, v in zip(header, row):
                cols[h].append(v)
    out, kinds = {}, {}
    for h, vals in cols.items():
        nums = []
        n_num = n_time = 0
        for v in vals:
            try:
                nums.append(float(v)); n_num += 1
            except ValueError:
                s = _to_seconds(v) if v.strip() else None
                if s is not None:
                    nums.append(s); n_time += 1
                else:
                    nums.append(np.nan)
        if vals and (n_num + n_time) >= 0.8 * len(vals):
            out[h] = np.array(nums, float)
            kinds[h] = "time" if n_time > n_num else "number"
        else:
            out[h] = np.array(vals, object)
            kinds[h] = "text"
    return out, kinds


# 역할 -> (정규식, 기본 단위). 순서가 중요: 앞에서 먼저 잡힌 열은 다시 쓰지 않는다.
ROLE_PATTERNS = [
    ("time", r"^(t|time|timestamp|datetime|date_time|elapsed.*|sec(ond)?s?|min(ute)?s?|hours?|sol)\b|time", "s"),
    ("hr", r"heart|\bhr\b|^hr|bpm|pulse", "bpm"),
    ("vo2", r"vo2|o2.?uptake|oxygen.?consumption", "l/min"),
    ("mr", r"metab|\bmr\b|^mr|met.?rate|energy.?expend|\bee\b|work.?rate|btu", "W"),
    ("speed", r"speed|velocity|\bv\b|pace", "m/s"),
    ("grade", r"grade|slope|incline", "%"),
    ("surface", r"surface|terrain|ground|soil|class|condition", ""),
    ("tank_p", r"press|psi|kpa|mpa", "kPa"),
    ("tank_t", r"tank.?t|gas.?t", "K"),
    ("dose", r"dose|gy\b|gray|sv\b|sievert|rad\b|radiation", "uGy/h"),
    ("temp", r"temp|air.?t", "C"),
    ("lat", r"^lat|latitude", "deg"),
    ("lon", r"^lon|longitude", "deg"),
    ("elev", r"elev|altitude|height|\bz\b", "m"),
    ("o2_mass", r"o2.?(mass|g\b|kg)|oxygen.?(mass|remain)", "g"),
    ("water", r"water|feedwater|coolant", "g"),
]
UNIT_RE = re.compile(r"[\(\[]([^\)\]]+)[\)\]]")


def detect_roles(header, kinds=None, override: dict | None = None):
    roles, used = {}, set()
    if override:
        for role, col in override.items():
            if col in header:
                roles[role] = {"column": col, "unit": _unit_of(col, role)}
                used.add(col)
    for role, pat, _ in ROLE_PATTERNS:
        if role in roles:
            continue
        for h in header:
            if h in used:
                continue
            if kinds and role != "surface" and kinds.get(h) == "text":
                continue
            if kinds and role == "surface" and kinds.get(h) != "text":
                continue
            if re.search(pat, h.lower()):
                roles[role] = {"column": h, "unit": _unit_of(h, role)}
                used.add(h)
                break
    return roles


def _unit_of(col: str, role: str) -> str:
    m = UNIT_RE.search(col)
    u = (m.group(1) if m else col).lower().replace("µ", "u").replace("μ", "u").replace(" ", "")
    if role == "mr":
        if "btu" in u: return "BTU/h"
        if "kcal" in u: return "kcal/h" if "/h" in u or "hr" in u else "kcal/min"
        return "W"
    if role == "vo2":
        if "ml/kg" in u: return "ml/kg/min"
        if "ml" in u: return "ml/min"
        return "l/min"
    if role == "speed":
        if "km/h" in u or "kph" in u: return "km/h"
        if "mph" in u: return "mph"
        return "m/s"
    if role == "grade":
        if "deg" in u or "°" in u: return "deg"
        return "%"
    if role == "dose":
        for cand in ("ugy/h", "mgy/day", "mgy/d", "ugy/day", "usv/h", "msv/day", "msv/d", "mgy/h", "gy/s"):
            if cand in u:
                return cand.replace("/d", "/day").replace("/dayay", "/day")
        if "sv" in u: return "usv/h"
        return "ugy/h"
    if role == "tank_p":
        for cand in ("mpa", "kpa", "psi", "pa"):
            if cand in u: return cand
        return "kpa"
    if role == "time":
        if "min" in u: return "min"
        if "hour" in u or u in ("h", "hr"): return "h"
        if "sol" in u: return "sol"
        return "s"
    return dict((r, d) for r, _, d in ROLE_PATTERNS).get(role, "")


def to_si(values, role: str, unit: str, body_kg: float | None = None):
    """역할별로 계산에 쓰는 단위로 바꾼다: mr -> W, speed -> m/s, grade -> %, dose -> mSv/day 가 아니라 원래 계열 유지."""
    v = np.asarray(values, float)
    if role == "mr":
        return {"BTU/h": v * 0.29307107, "kcal/h": v * 1.16222, "kcal/min": v * 69.733}.get(unit, v)
    if role == "vo2":                              # 20.1 kJ/L O2 (RER ~0.85)
        if unit == "ml/kg/min":
            if not body_kg:
                raise ValueError("VO2가 ml/kg/min이라 체중이 필요합니다 (--body-kg)")
            v = v * body_kg / 1000
        elif unit == "ml/min":
            v = v / 1000
        return v * 20100 / 60                       # W
    if role == "speed":
        return {"km/h": v / 3.6, "mph": v * 0.44704}.get(unit, v)
    if role == "grade":
        return np.tan(np.radians(v)) * 100 if unit == "deg" else v
    if role == "time":
        return {"min": v * 60, "h": v * 3600, "sol": v * 88775.244}.get(unit, v)
    if role == "tank_p":
        return {"mpa": v * 1e6, "kpa": v * 1e3, "psi": v * 6894.757}.get(unit, v)
    return v


# ---------------------------------------------------------------- 지형
def _parse_pds_label(text: str) -> dict:
    lab = {}
    for line in text.splitlines():
        m = re.match(r"\s*([A-Z0-9_^:]+)\s*=\s*(.+?)\s*$", line)
        if m and m.group(1) not in lab:
            lab[m.group(1)] = m.group(2).strip().strip('"')
    return lab


def _num(s):
    m = re.search(r"-?[\d.]+(?:[eE][-+]?\d+)?", str(s))
    return float(m.group(0)) if m else None


def load_dem(path: str, max_pixels: int = 60_000_000):
    """반환: h (float64, NoData는 nan), pixel_m, info(dict)."""
    ext = os.path.splitext(path)[1].lower()
    info = {"path": path, "format": None}
    if ext == ".npy":
        h = np.load(path).astype(np.float64)
        meta_p = os.path.splitext(path)[0] + ".json"
        px = json.load(open(meta_p)).get("pixel_m") if os.path.exists(meta_p) else None
        info["format"] = "npy"
        return h, px, info
    if ext in (".img", ".lbl"):
        img = path if ext == ".img" else _sibling(path, (".IMG", ".img"))
        lbl_p = _sibling(img, (".LBL", ".lbl"))
        head = open(lbl_p or img, "rb").read(65536).decode("latin-1", "replace")
        lab = _parse_pds_label(head)
        lines, samples = int(_num(lab["LINES"])), int(_num(lab["LINE_SAMPLES"]))
        bits = int(_num(lab.get("SAMPLE_BITS", 32)))
        st = lab.get("SAMPLE_TYPE", "PC_REAL")
        dtype = {("PC_REAL", 32): "<f4", ("IEEE_REAL", 32): ">f4", ("MSB_INTEGER", 16): ">i2",
                 ("LSB_INTEGER", 16): "<i2", ("PC_REAL", 64): "<f8"}.get((st, bits), "<f4")
        offset = 0
        if not lbl_p:                               # 라벨이 영상 안에 붙어 있음
            rec = int(_num(lab.get("RECORD_BYTES", 0)))
            ptr = lab.get("^IMAGE", "1")
            offset = int(_num(ptr) - 1) * rec if "<BYTES>" not in ptr else int(_num(ptr)) - 1
        if lines * samples > max_pixels:
            raise ValueError(f"지형이 너무 큽니다 ({lines}x{samples}). 잘라서 쓰세요(max_pixels).")
        h = np.memmap(img, dtype=dtype, mode="r", offset=offset, shape=(lines, samples)).astype(np.float64)
        miss = lab.get("MISSING_CONSTANT")
        h[(h < -1e30) | (h > 1e30)] = np.nan
        if miss and not miss.startswith("16#"):
            h[h == _num(miss)] = np.nan
        scale = lab.get("MAP_SCALE")
        px = _num(scale) * (1000 if scale and "KM" in scale.upper() else 1) if scale else None
        info.update(format="PDS IMG", label=os.path.basename(lbl_p or img), sample_type=st)
        return h, px, info
    if ext in (".tif", ".tiff"):
        try:
            import rasterio                         # 있으면 좌표계까지 정확히 읽는다
            with rasterio.open(path) as ds:
                h = ds.read(1).astype(np.float64)
                if ds.nodata is not None:
                    h[h == ds.nodata] = np.nan
                px = abs(ds.transform.a)
                info.update(format="GeoTIFF (rasterio)", crs=str(ds.crs))
                return h, px, info
        except ImportError:
            pass
        from PIL import Image
        Image.MAX_IMAGE_PIXELS = None
        im = Image.open(path)
        h = np.asarray(im, dtype=np.float64)
        tags = getattr(im, "tag_v2", {})
        px = None
        if 33550 in tags:                           # ModelPixelScaleTag
            px = float(tags[33550][0])
        nod = tags.get(42113)                       # GDAL_NODATA
        if nod is not None:
            h[h == float(str(nod).strip("\x00"))] = np.nan
        h[(h < -1e30) | (h > 1e30)] = np.nan
        info.update(format=f"GeoTIFF (Pillow, mode {im.mode})", georef=33922 in tags)
        return h, px, info
    raise ValueError(f"지형 형식을 모릅니다: {path}")


def _sibling(path, exts):
    stem = os.path.splitext(path)[0]
    for e in exts:
        if os.path.exists(stem + e):
            return stem + e
    return None


# ---------------------------------------------------------------- 영상 + 마스크
IMG_EXT = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".jp2")
MASK_DIR = re.compile(r"^(masks?|labels?|annotations?|gt|ground_?truth|segmentations?)$", re.I)


def find_image_mask_pairs(root: str):
    files = [p for p in glob.glob(os.path.join(root, "**", "*"), recursive=True)
             if os.path.splitext(p)[1].lower() in IMG_EXT]
    masks, images = {}, {}
    for p in files:
        rel = os.path.relpath(p, root)
        stem = os.path.splitext(os.path.basename(p))[0]
        dirs = os.path.dirname(rel).replace("\\", "/").split("/")
        is_mask = any(MASK_DIR.match(d) for d in dirs) or bool(re.search(r"_(mask|label|gt|seg)$", stem, re.I))
        key = re.sub(r"_(mask|label|gt|seg)$", "", stem, flags=re.I)
        (masks if is_mask else images)[key] = p
    pairs = [(images[k], masks[k]) for k in sorted(images) if k in masks]
    return pairs, sorted(set(images) - set(masks)), sorted(set(masks) - set(images))

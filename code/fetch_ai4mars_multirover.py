"""
여러 로버를 섞은 학습 데이터 — "데이터셋을 여러 개 결합하면 어떨까?" 실험용

지금까지 쓴 AI4Mars 서브셋은 전부 MSL(Curiosity) Navcam 한 종류였다. 그런데 AI4Mars
병합 아카이브에는 사실 MER(Spirit/Opportunity, 2004~)·M2020(Perseverance) 로버의
라벨도 같은 4-클래스(NAV) 스킴으로 섞여 있다 — 카메라·시대·해상도가 전혀 다른 로버들이다.

기존 MSL-only 베이스라인(299train/60val, val mIoU 0.643)과 **정확히 같은 총 예산**
(train 300 / val 60)을 쓰되, 이번엔 MSL 150 + MER 100 + M2020 50 (val도 동일 비율)으로
나눠 받는다 — "데이터 양은 그대로 두고 출처만 다양화하면 무슨 일이 일어나는가"를 보는
공정한 비교를 위해서다.

MER/M2020은 공식 매니페스트에 이미지 경로가 비어 있어서(마스크 경로만 존재), 마스크
파일명에서 "_mergedN" 접미사를 뗀 뒤 이미지 파일명과 접두사 매칭(fuzzy prefix match)으로
직접 찾아야 한다 — 그 매칭 로직도 이 스크립트에 포함했다.
"""
from __future__ import annotations

import csv
import json
import os
import random
import re
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(__file__))
from ai4mars_remote_zip import load_central_directory, extract

MANIFEST_URL = ("https://raw.githubusercontent.com/Jacob-Miller-s/AI4Mars/main/"
                 "artifacts/manifests/ai4mars_dataset_manifest.csv")
MANIFEST_CACHE = "/tmp/full_manifest.csv"

ZIP_PREFIX = "ai4mars-dataset-merged-0.6/"
OUT_DIR = "../data/ai4mars_multirover"
MSL_SUBSET_DIR = "../data/ai4mars_subset"  # 기존에 받아둔 MSL 서브셋 재사용

N_TRAIN_PER_SOURCE = {"msl": 150, "mer": 100, "m2020": 50}
N_VAL_PER_SOURCE = {"msl": 30, "mer": 20, "m2020": 10}
BIG_ROCK_FRACTION = 0.45
RNG_SEED = 11
REQUEST_DELAY_S = 0.35


def ensure_manifest():
    if os.path.exists(MANIFEST_CACHE):
        return
    print("전체 매니페스트 다운로드...")
    urllib.request.urlretrieve(MANIFEST_URL, MANIFEST_CACHE)


def stem_of(path: str) -> str:
    return os.path.splitext(os.path.basename(path))[0]


def strip_merged_suffix(stem: str) -> str:
    return re.sub(r"_merged\d+$", "", stem)


def commonprefix_len(a: str, b: str) -> int:
    n = min(len(a), len(b))
    for i in range(n):
        if a[i] != b[i]:
            return i
    return n


def build_image_index(entries: dict) -> dict:
    """mer/m2020 이미지 파일을 stem 앞 12글자로 버킷팅 — fuzzy prefix 매칭용."""
    from collections import defaultdict
    idx = defaultdict(list)
    for k in entries:
        if not k.startswith(ZIP_PREFIX):
            continue
        rel = k[len(ZIP_PREFIX):]
        if not (rel.startswith("mer/images/") or rel.startswith("m2020/images/")):
            continue
        if rel.endswith("/") or not re.search(r"\.(jpg|jpeg)$", rel, re.IGNORECASE):
            continue
        s = stem_of(rel)
        idx[s[:12]].append((s, k))
    return dict(idx)


def match_image_for_mask(mask_base: str, image_index: dict) -> str | None:
    candidates = image_index.get(mask_base[:12], [])
    best_stem, best_key, best_len = None, None, 0
    for stem, key in candidates:
        L = commonprefix_len(mask_base, stem)
        if L > best_len:
            best_len, best_stem, best_key = L, stem, key
    if best_key and best_len >= max(10, int(0.6 * min(len(mask_base), len(best_stem)))):
        return best_key
    return None


def collect_mer_m2020_candidates(entries: dict, image_index: dict) -> dict:
    """미션별 {(mask_key, img_key, stem, has_big_rock)} 후보 목록."""
    with open(MANIFEST_CACHE, newline="") as f:
        reader = csv.DictReader(f)
        rows = [r for r in reader if r["dataset_relative_mask_path"] and r["label_scheme"] == "NAV"
                and r["mission"] in ("mer", "m2020")]

    by_mission = {"mer": [], "m2020": []}
    for r in rows:
        mask_rel = r["dataset_relative_mask_path"]
        mask_key = ZIP_PREFIX + mask_rel
        if mask_key not in entries:
            continue
        mask_base = strip_merged_suffix(stem_of(mask_rel))
        img_key = match_image_for_mask(mask_base, image_index)
        if img_key is None:
            continue
        try:
            counts = json.loads(r["per_class_pixel_counts_json"])
        except (KeyError, json.JSONDecodeError):
            counts = {}
        by_mission[r["mission"]].append({
            "mask_key": mask_key, "img_key": img_key, "stem": mask_base,
            "has_big_rock": counts.get("3", 0) > 500,
        })
    return by_mission


def select(cands: list, n: int, rng: random.Random) -> list:
    with_rock = [c for c in cands if c["has_big_rock"]]
    without_rock = [c for c in cands if not c["has_big_rock"]]
    rng.shuffle(with_rock); rng.shuffle(without_rock)
    n_rock = min(int(n * BIG_ROCK_FRACTION), len(with_rock))
    selected = with_rock[:n_rock] + without_rock[:n - n_rock]
    rng.shuffle(selected)
    return selected


def download_remote_pairs(items: list, entries: dict, img_dir: str, mask_dir: str):
    os.makedirs(img_dir, exist_ok=True)
    os.makedirs(mask_dir, exist_ok=True)
    ok, skipped = 0, 0
    for i, item in enumerate(items):
        stem = item["stem"]
        img_ext = os.path.splitext(item["img_key"])[1]
        img_out = f"{img_dir}/{stem}{img_ext}"
        mask_out = f"{mask_dir}/{stem}.png"
        if os.path.exists(img_out) and os.path.exists(mask_out):
            ok += 1
            continue
        try:
            img_bytes = extract(entries[item["img_key"]]); time.sleep(REQUEST_DELAY_S)
            mask_bytes = extract(entries[item["mask_key"]]); time.sleep(REQUEST_DELAY_S)
        except Exception as e:
            print(f"  [실패, 건너뜀] {stem}: {e}")
            skipped += 1
            continue
        with open(img_out, "wb") as f:
            f.write(img_bytes)
        with open(mask_out, "wb") as f:
            f.write(mask_bytes)
        ok += 1
        if (i + 1) % 20 == 0:
            print(f"  {i + 1}/{len(items)} ({ok}개 저장, {skipped}개 누락)")
    print(f"  완료: {ok}개 저장, {skipped}개 누락")


def copy_msl_subset(n: int, split: str, rng: random.Random, img_dir: str, mask_dir: str):
    """이미 받아둔 MSL 서브셋에서 n장을 골라 새 폴더로 복사(재다운로드 없음)."""
    import shutil
    src_img_dir = f"{MSL_SUBSET_DIR}/{split}/images"
    src_mask_dir = f"{MSL_SUBSET_DIR}/{split}/masks"
    stems = [os.path.splitext(f)[0] for f in os.listdir(src_img_dir)]
    rng.shuffle(stems)
    chosen = stems[:n]
    os.makedirs(img_dir, exist_ok=True)
    os.makedirs(mask_dir, exist_ok=True)
    for stem in chosen:
        img_src = next(f for f in os.listdir(src_img_dir) if os.path.splitext(f)[0] == stem)
        shutil.copy(f"{src_img_dir}/{img_src}", f"{img_dir}/{img_src}")
        shutil.copy(f"{src_mask_dir}/{stem}.png", f"{mask_dir}/{stem}.png")
    print(f"  MSL {split}: {len(chosen)}장 복사 (기존 서브셋에서 재사용, 재다운로드 없음)")


def main():
    rng = random.Random(RNG_SEED)

    print("MSL 서브셋 재사용 (train/val 일부 복사)...")
    copy_msl_subset(N_TRAIN_PER_SOURCE["msl"], "train", rng, f"{OUT_DIR}/train/images", f"{OUT_DIR}/train/masks")
    copy_msl_subset(N_VAL_PER_SOURCE["msl"], "val", rng, f"{OUT_DIR}/val/images", f"{OUT_DIR}/val/masks")

    print("\n전체 매니페스트 로딩...")
    ensure_manifest()

    print("원격 zip 중앙 디렉터리 로딩...")
    entries = load_central_directory()
    image_index = build_image_index(entries)

    print("\nMER/M2020 후보 매칭...")
    candidates = collect_mer_m2020_candidates(entries, image_index)
    for mission, cands in candidates.items():
        print(f"  {mission}: 후보 {len(cands)}개 (big_rock 포함 {sum(1 for c in cands if c['has_big_rock'])}개)")

    for mission in ("mer", "m2020"):
        train_sel = select(candidates[mission], N_TRAIN_PER_SOURCE[mission], rng)
        val_pool = [c for c in candidates[mission] if c not in train_sel]
        val_sel = select(val_pool, N_VAL_PER_SOURCE[mission], rng)

        print(f"\n{mission} train {len(train_sel)}쌍 다운로드...")
        download_remote_pairs(train_sel, entries, f"{OUT_DIR}/train/images", f"{OUT_DIR}/train/masks")
        print(f"{mission} val {len(val_sel)}쌍 다운로드...")
        download_remote_pairs(val_sel, entries, f"{OUT_DIR}/val/images", f"{OUT_DIR}/val/masks")

    n_train = len(os.listdir(f"{OUT_DIR}/train/images"))
    n_val = len(os.listdir(f"{OUT_DIR}/val/images"))
    print(f"\n완료. train {n_train}장, val {n_val}장 (data/ai4mars_multirover/)")


if __name__ == "__main__":
    main()

"""
AI4Mars 학습용 서브셋 다운로드 — 16GB 원본 zip에서 필요한 수백 장만

공식 데이터셋 매니페스트(train_nav.csv / val_nav.csv, Jacob-Miller-s/AI4Mars 저장소에서
가져옴)를 기준으로, big_rock 라벨이 실제로 포함된 이미지를 우선해 샘플링한다 — 지금까지
earlier boulder_detection_no_labels.py 실험에서 "라벨 없이 그림자로 탐지하면 big_rock을
잘 못 찾는다(IoU 0.120)"는 걸 확인했으니, 실제 학습 데이터에도 big_rock이 충분히
있어야 그 문제를 모델이 배울 기회가 생긴다.
"""
from __future__ import annotations

import csv
import json
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
from ai4mars_remote_zip import load_central_directory, extract

OUT_DIR = "../data/ai4mars_subset"
ZIP_PREFIX = "ai4mars-dataset-merged-0.6/"

N_TRAIN = 300
N_VAL = 60
BIG_ROCK_FRACTION = 0.45  # big_rock이 있는 이미지를 이 비율만큼 우선 포함
RNG_SEED = 7
REQUEST_DELAY_S = 0.35  # Zenodo rate limit(약 130req/분) 아래로 유지


def read_manifest(path: str) -> list[dict]:
    rows = []
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            rows.append(row)
    return rows


def has_big_rock(row: dict) -> bool:
    try:
        counts = json.loads(row["per_class_pixel_counts_json"])
    except (KeyError, json.JSONDecodeError):
        return False
    return counts.get("3", 0) > 500  # 아주 작은 노이즈성 라벨은 제외


def select_subset(rows: list[dict], n: int, rng: random.Random) -> list[dict]:
    with_rock = [r for r in rows if has_big_rock(r)]
    without_rock = [r for r in rows if not has_big_rock(r)]
    rng.shuffle(with_rock)
    rng.shuffle(without_rock)

    n_rock = min(int(n * BIG_ROCK_FRACTION), len(with_rock))
    n_other = n - n_rock
    selected = with_rock[:n_rock] + without_rock[:n_other]
    rng.shuffle(selected)
    print(f"  선택됨: {len(selected)}장 (big_rock 포함 {n_rock}장, 나머지 {len(selected) - n_rock}장)")
    return selected


def download_pairs(rows: list[dict], entries: dict, img_dir: str, mask_dir: str):
    os.makedirs(img_dir, exist_ok=True)
    os.makedirs(mask_dir, exist_ok=True)
    ok, skipped = 0, 0
    for i, row in enumerate(rows):
        img_rel = row["dataset_relative_image_path"]
        mask_rel = row["dataset_relative_mask_path"]
        img_key, mask_key = ZIP_PREFIX + img_rel, ZIP_PREFIX + mask_rel

        if img_key not in entries or mask_key not in entries:
            skipped += 1
            continue

        stem = row["stable_source_image_id"]
        img_ext = os.path.splitext(img_rel)[1]
        img_out = f"{img_dir}/{stem}{img_ext}"
        mask_out = f"{mask_dir}/{stem}.png"
        if os.path.exists(img_out) and os.path.exists(mask_out):
            ok += 1
            continue

        try:
            img_bytes = extract(entries[img_key]); time.sleep(REQUEST_DELAY_S)
            mask_bytes = extract(entries[mask_key]); time.sleep(REQUEST_DELAY_S)
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
            print(f"  {i + 1}/{len(rows)} ({ok}개 저장, {skipped}개 누락)")
    print(f"  완료: {ok}개 저장, {skipped}개 누락")


def main():
    rng = random.Random(RNG_SEED)

    print("매니페스트 로딩...")
    train_rows = read_manifest("/tmp/train_nav.csv")
    val_rows = read_manifest("/tmp/val_nav.csv")
    print(f"  train {len(train_rows)}행, val {len(val_rows)}행")

    print("\n학습용 서브셋 선택 (train)...")
    train_sel = select_subset(train_rows, N_TRAIN, rng)
    print("검증용 서브셋 선택 (val)...")
    val_sel = select_subset(val_rows, N_VAL, rng)

    print("\n원격 zip 중앙 디렉터리 로딩...")
    entries = load_central_directory()

    print(f"\ntrain {len(train_sel)}쌍 다운로드...")
    download_pairs(train_sel, entries, f"{OUT_DIR}/train/images", f"{OUT_DIR}/train/masks")

    print(f"\nval {len(val_sel)}쌍 다운로드...")
    download_pairs(val_sel, entries, f"{OUT_DIR}/val/images", f"{OUT_DIR}/val/masks")

    print("\n완료.")


if __name__ == "__main__":
    main()

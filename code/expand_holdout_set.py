"""
held-out 평가셋 3장 -> 20장 확장 — 통계적 취약점을 고친다

지금까지 모든 big_rock held-out 지표(그림자 CV IoU=0.120, 모델 단독=0.052,
캐스케이드 융합=0.170)는 data/ai4mars_samples/의 단 3장에서 나왔는데, 다시 뜯어보니
그중 2장이 "정답 big_rock 비율 0%"인 퇴화 샘플이었다 — 셋 중 하나는 평균 집계 시
NaN으로 조용히 빠지고, 나머지 하나는 항상 IoU 0으로만 기여한다. 결국 세 지표 전부
사실상 이미지 1장(NLB_486372898...)의 점수가 좌우한 것 — N=3은 애초에 통계적으로
의미가 없었다.

고치는 방법: fetch_ai4mars_subset.py가 썼던 것과 같은 Zenodo 부분 다운로드 파이프라인
(ai4mars_remote_zip.py)으로, train/val 서브셋 및 기존 3장과 겹치지 않는 새 이미지를
val_nav.csv 매니페스트에서 더 뽑는다. big_rock 라벨이 실제로 있는 이미지를 우선 섞어
(기존 서브셋 구축 때와 같은 BIG_ROCK_FRACTION 비율) 퇴화 샘플 비중을 낮춘다.

주의: 여기서 뽑은 20장은 평가 전용이다 — cascade_fusion_detection.py가 이미 선택한
임계값(0.20, val set 60장에서 튠됨)을 그대로 재사용하고, 이 20장에서 새로 튜닝하지
않는다. 그래야 진짜 held-out 비교가 유지된다.
"""
from __future__ import annotations

import csv
import json
import os
import random
import time

from ai4mars_remote_zip import load_central_directory, extract

OUT_DIR = "../data/ai4mars_holdout_v2"
ZIP_PREFIX = "ai4mars-dataset-merged-0.6/"

N_HOLDOUT = 20
BIG_ROCK_FRACTION = 0.7  # 기존 3장 중 2장이 big_rock 0%였던 퇴화 문제를 고치려고 비중을 높임
RNG_SEED = 11  # fetch_ai4mars_subset.py(SEED=7)와 다른 시드 -> 겹칠 가능성 더 낮춤
REQUEST_DELAY_S = 0.35


def read_manifest(path: str) -> list[dict]:
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def has_big_rock(row: dict) -> bool:
    try:
        counts = json.loads(row["per_class_pixel_counts_json"])
    except (KeyError, json.JSONDecodeError):
        return False
    return counts.get("3", 0) > 500


def already_used_stems() -> set[str]:
    used = set()
    for d in ["../data/ai4mars_subset/train/images", "../data/ai4mars_subset/val/images"]:
        if os.path.isdir(d):
            for fn in os.listdir(d):
                used.add(os.path.splitext(fn)[0])
    if os.path.isdir("../data/ai4mars_samples"):
        for fn in os.listdir("../data/ai4mars_samples"):
            if fn.endswith(".jpg"):
                used.add(os.path.splitext(fn)[0])
    return used


def select_holdout(rows: list[dict], exclude: set[str], n: int, rng: random.Random) -> list[dict]:
    candidates = [r for r in rows if r["stable_source_image_id"] not in exclude]
    with_rock = [r for r in candidates if has_big_rock(r)]
    without_rock = [r for r in candidates if not has_big_rock(r)]
    rng.shuffle(with_rock)
    rng.shuffle(without_rock)

    n_rock = min(int(n * BIG_ROCK_FRACTION), len(with_rock))
    n_other = n - n_rock
    selected = with_rock[:n_rock] + without_rock[:n_other]
    rng.shuffle(selected)
    print(f"  선택됨: {len(selected)}장 (big_rock 포함 {n_rock}장, 나머지 {len(selected) - n_rock}장) "
          f"— 후보 풀 {len(candidates)}장 중 (기존 {len(exclude)}장 제외)")
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
            print(f"  [누락, 건너뜀] {row['stable_source_image_id']}")
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
        print(f"  {i + 1}/{len(rows)}: {stem} 저장")
    print(f"  완료: {ok}개 저장, {skipped}개 누락")


def main():
    rng = random.Random(RNG_SEED)

    print("매니페스트 로딩...")
    val_rows = read_manifest("/tmp/val_nav.csv")
    exclude = already_used_stems()
    print(f"  val_nav {len(val_rows)}행, 이미 사용된 stem {len(exclude)}개 제외 대상")

    print("\nheld-out 확장 세트 선택...")
    selected = select_holdout(val_rows, exclude, N_HOLDOUT, rng)

    print("\n원격 zip 중앙 디렉터리 로딩...")
    entries = load_central_directory()

    print(f"\n{len(selected)}쌍 다운로드 -> {OUT_DIR}...")
    download_pairs(selected, entries, f"{OUT_DIR}/images", f"{OUT_DIR}/masks")

    with open(f"{OUT_DIR}/manifest_selected.json", "w") as f:
        json.dump([{"stem": r["stable_source_image_id"],
                    "has_big_rock": has_big_rock(r)} for r in selected], f, indent=2)
    print(f"\nsaved {OUT_DIR}/manifest_selected.json")


if __name__ == "__main__":
    main()

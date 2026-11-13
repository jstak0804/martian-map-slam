"""
정답을 알고 만든 가짜 해커톤 데이터. 파이프라인이 끝까지 돌고 정답을 되찾는지 미리 확인하는 용도다.
실제 측정값이 아니므로 여기서 나온 보정값은 활성화가 거부된다(SYNTHETIC.txt 표식).

    python -m hackathon.make_synthetic --out ../data/hackathon_synthetic

만드는 것 (이름·단위를 일부러 제각각으로):
  eva_physio.csv   심박, 대사량(W), 속도, 경사, 지면 — 정답: HR 회귀 a=−300, b=16 BTU/h, 지면 η, 속도식
  rad_dose.csv     시간(h), 선량률(uGy/h) — 정답: 배경 9 uGy/h (Q 3.05 -> 0.659 mSv/day), SPE x4 한 건
  site_dem.tif     2 m 지형 GeoTIFF(6 km x 6 km,(ModelPixelScale 태그) — 언덕, 크레이터, 1 m급 요철
  seg/images, seg/masks   128 px 영상·마스크 24쌍 (soil 0, bedrock 1, sand 2, big_rock 3)
  notes.md         문서 예시
"""
from __future__ import annotations

import argparse
import csv
import json
import os

import numpy as np
from PIL import Image, TiffImagePlugin

TRUTH = {"hr_a_btu_h": -300.0, "hr_b_btu_h_per_bpm": 16.0,     # 지구 보행에서 HR 100 -> 381 W, 170 -> 709 W
         "eta": {"regolith": 1.15, "rock field": 1.40}, "sand_a": 1.8, "sand_b": 1.0,
         "speed_v0": 1.30, "speed_c": 0.015, "g": 1.0, "body_kg": 75.0, "load_kg": 20.0,
         "dose_bg_ugy_h": 9.0, "spe_peak_multiplier": 4.0}


def pandolf(v, grade, eta, g=1.0, W=75.0, L=20.0):
    W, L = W * g, L * g
    return 1.5 * W + 2 * (W + L) * (L / W) ** 2 + eta * (W + L) * (1.5 * v ** 2 + 0.35 * v * np.maximum(grade, 0))


def physio(path, rng):
    rows = []
    t = 0
    for session, surface in enumerate(["regolith", "rock field", "sand", "regolith", "sand"]):
        grade_plan = np.clip(np.cumsum(rng.normal(0, 0.5, 360)) + rng.uniform(0, 4), -6, 8)
        for g in grade_plan:                       # 10초 간격 1시간
            v = TRUTH["speed_v0"] - TRUTH["speed_c"] * max(g, 0) + rng.normal(0, 0.05)
            if surface == "sand":
                v = rng.uniform(0.8, 1.1)          # 모래: 속도를 바꿔 가며 (b 추정용), 완만한 곳만
                g = float(np.clip(g, -2, 3))
            v = max(v, 0.4)
            eta = TRUTH["sand_a"] + TRUTH["sand_b"] / v ** 2 if surface == "sand" else TRUTH["eta"][surface]
            mr = pandolf(v, g, eta) * (1 + rng.normal(0, 0.06))
            hr = (mr / 0.29307107 - TRUTH["hr_a_btu_h"]) / TRUTH["hr_b_btu_h_per_bpm"] + rng.normal(0, 4)
            rows.append([t, round(hr, 1), round(mr, 1), round(v, 3), round(g, 2), surface])
            t += 10
        t += 1800
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Elapsed (s)", "Heart Rate (bpm)", "Metabolic Rate (W)", "Walking Speed (m/s)", "Grade (%)", "Surface"])
        w.writerows(rows)


def dose(path, rng):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["hour", "dose_rate (uGy/h)"])
        for h in range(240):
            r = TRUTH["dose_bg_ugy_h"] * (1 + rng.normal(0, 0.05))
            if 100 <= h < 112:
                r *= 1 + (TRUTH["spe_peak_multiplier"] - 1) * np.sin(np.pi * (h - 100 + 0.5) / 12)
            w.writerow([h, round(r, 3)])


def dem(path, rng, n=3000, px=2.0):
    y, x = np.mgrid[0:n, 0:n] * px
    h = 60 * np.sin(x / 400) * np.cos(y / 350) + 0.05 * x
    cy, cx, R = 3600, 2300, 400                      # 크레이터
    r = np.hypot(x - cx, y - cy)
    h += np.where(r < R, -25 * (1 - (r / R) ** 2), 6 * np.exp(-((r - R) / 25) ** 2))
    h += rng.normal(0, 0.25, h.shape)                # 1 m급 요철
    h[:12, :30] = -3.4e38                            # NoData 일부
    info = TiffImagePlugin.ImageFileDirectory_v2()
    info[33550] = (px, px, 0.0)
    info.tagtype[33550] = 12
    Image.fromarray(h.astype(np.float32)).save(path, tiffinfo=info)


def seg(root, rng, n=24, size=128):
    os.makedirs(f"{root}/images", exist_ok=True); os.makedirs(f"{root}/masks", exist_ok=True)
    yy, xx = np.mgrid[0:size, 0:size]
    for i in range(n):
        m = np.zeros((size, size), np.uint8)
        img = 0.45 + 0.05 * rng.standard_normal((size, size))          # soil: 중간 밝기, 잔무늬
        for _ in range(2):                                             # bedrock: 밝은 판
            x0, y0 = rng.integers(0, size - 40, 2)
            m[y0:y0 + 40, x0:x0 + 50] = 1
        for _ in range(2):                                             # sand: 어둡고 매끈
            cx, cy, rr = *rng.integers(10, size - 10, 2), rng.integers(12, 28)
            m[(xx - cx) ** 2 + (yy - cy) ** 2 < rr ** 2] = 2
        for _ in range(4):                                             # big rock: 아주 밝은 작은 원
            cx, cy, rr = *rng.integers(5, size - 5, 2), rng.integers(4, 9)
            m[(xx - cx) ** 2 + (yy - cy) ** 2 < rr ** 2] = 3
        img = np.where(m == 1, 0.65 + 0.03 * rng.standard_normal(m.shape), img)
        img = np.where(m == 2, 0.25 + 0.01 * rng.standard_normal(m.shape), img)
        img = np.where(m == 3, 0.9, img)
        Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)).save(f"{root}/images/scene_{i:03d}.png")
        Image.fromarray(m).save(f"{root}/masks/scene_{i:03d}_mask.png")


def main(out):
    os.makedirs(out, exist_ok=True)
    rng = np.random.default_rng(42)
    physio(f"{out}/eva_physio.csv", rng)
    dose(f"{out}/rad_dose.csv", rng)
    dem(f"{out}/site_dem.tif", rng)
    seg(f"{out}/seg", rng)
    with open(f"{out}/notes.md", "w", encoding="utf-8") as f:
        f.write("# 가짜 해커톤 데이터\n\n파이프라인 점검용. 실제 측정값 아님.\n")
    with open(f"{out}/SYNTHETIC.txt", "w") as f:
        f.write("synthetic test data - do not activate calibrations\n")
    with open(f"{out}/truth.json", "w") as f:
        json.dump(TRUTH, f, indent=1)
    print(f"가짜 데이터 -> {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="../data/hackathon_synthetic")
    main(ap.parse_args().out)

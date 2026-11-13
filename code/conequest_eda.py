"""
ConeQuest(Zenodo 10077410) 데이터셋 1단계 — 탐색적 분석(EDA)만 수행.
학습/파이프라인 통합은 하지 않음. 목적: 실제로 뭐가 들어있는지 직접 열어서 확인하고
2단계(U-Net 일반화 테스트)에 쓸 수 있는 형태인지 판단하기 위한 자료를 만든다.

데이터 구성(zip 내부 직접 확인 결과):
  <region>/input_dir/<id>.tif  — 512x512 그레이스케일(uint8) HiRISE/CTX 패치
  <region>/output_dir/<id>.tif — 512x512 이진 마스크(0/1) — 1=콘(cone) 픽셀
메타데이터 CSV(ConeQuest_data.csv, 13,686행)에 Region/Number of Cones/BM-1 Set(train/val/test) 등 포함.

가장 작은 region zip(E084_N12, Isidis Planitia, 17MB, 144쌍)만 받아서 확인했다 — 전체 9개 zip(총 1.8GB)은
다음 단계(U-Net 일반화 테스트)에서 실제로 필요한 만큼만 추가로 받는다.
"""
import csv
import json
import zipfile
from collections import Counter
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt

DATA_DIR = Path("../data/conequest")
OUT_DIR = Path("../outputs/conequest")
OUT_DIR.mkdir(parents=True, exist_ok=True)

ZIP_PATH = DATA_DIR / "E084_N12.zip"
CSV_PATH = DATA_DIR / "ConeQuest_data.csv"
EXTRACT_DIR = DATA_DIR / "E084_N12"


def extract_zip():
    if EXTRACT_DIR.exists() and len(list(EXTRACT_DIR.rglob("*.tif"))) == 288:
        print("already extracted:", EXTRACT_DIR)
        return
    with zipfile.ZipFile(ZIP_PATH) as zf:
        zf.extractall(DATA_DIR)
    print("extracted", len(list(EXTRACT_DIR.rglob("*.tif"))), "tif files ->", EXTRACT_DIR)


def load_csv_stats():
    with open(CSV_PATH, newline="") as f:
        rows = list(csv.DictReader(f))
    regions = Counter(r["Region"] for r in rows)
    splits = Counter(r["BM-1 Set"] or "(미배정)" for r in rows)
    n_pos = sum(1 for r in rows if r["Number of Cones"] not in ("0", "", None))
    stats = {
        "total_rows": len(rows),
        "region_counts": dict(regions),
        "split_counts_bm1": dict(splits),
        "positive_rows": n_pos,
        "positive_frac": n_pos / len(rows),
    }
    return stats, rows


def local_sample_stats():
    """E084_N12(로컬 다운로드본)에 한정된 통계 — input/output tif를 직접 읽어서 계산."""
    in_files = sorted((EXTRACT_DIR / "input_dir").glob("*.tif"))
    out_files = sorted((EXTRACT_DIR / "output_dir").glob("*.tif"))
    assert len(in_files) == len(out_files) == 144, f"expected 144/144, got {len(in_files)}/{len(out_files)}"
    pos_frac_per_sample = []
    n_positive_samples = 0
    for of in out_files:
        from PIL import Image
        m = np.array(Image.open(of))
        frac = float((m > 0).mean())
        pos_frac_per_sample.append(frac)
        if frac > 0:
            n_positive_samples += 1
    pos_frac_per_sample = np.array(pos_frac_per_sample)
    return {
        "n_samples": len(out_files),
        "n_positive_samples": n_positive_samples,
        "positive_sample_frac": n_positive_samples / len(out_files),
        "mean_pixel_pos_frac_over_positive_samples": float(pos_frac_per_sample[pos_frac_per_sample > 0].mean()),
        "mean_pixel_pos_frac_overall": float(pos_frac_per_sample.mean()),
    }


def style_ax(ax):
    ax.set_facecolor("#0b0e15")
    for s in ax.spines.values():
        s.set_color("#262d3d")
    ax.tick_params(colors="#a7aec1", labelsize=8)
    ax.grid(False)


def pick_examples():
    """양성(큰 콘)/양성(작은 콘)/음성 샘플 하나씩 고른다."""
    from PIL import Image
    out_files = sorted((EXTRACT_DIR / "output_dir").glob("*.tif"))
    scored = []
    for of in out_files:
        m = np.array(Image.open(of))
        scored.append((float((m > 0).mean()), of))
    scored.sort(key=lambda t: t[0])
    neg = scored[0]
    small_pos = next((t for t in scored if t[0] > 0.02), scored[len(scored) // 2])
    big_pos = scored[-1]
    return [("음성(콘 없음)", neg), ("양성·작은 콘", small_pos), ("양성·큰 콘", big_pos)]


def plot_overview(global_stats, local_stats, examples):
    from PIL import Image
    fig = plt.figure(figsize=(13, 7.5), facecolor="#0b0e15")
    gs = fig.add_gridspec(3, 5, width_ratios=[1, 1, 1, 0.08, 1.6], height_ratios=[1, 1, 1],
                           hspace=0.35, wspace=0.25)

    for row, (label, (frac, out_path)) in enumerate(examples):
        in_path = EXTRACT_DIR / "input_dir" / out_path.name
        img = np.array(Image.open(in_path))
        mask = np.array(Image.open(out_path))
        overlay = np.stack([img, img, img], axis=-1).astype(np.float32)
        overlay[mask > 0] = [224, 145, 122]  # RUST
        overlay = overlay.astype(np.uint8)

        label_en = {"음성(콘 없음)": "negative (no cone)",
                    "양성·작은 콘": "positive, small cone",
                    "양성·큰 콘": "positive, large cone"}[label]
        ax0 = fig.add_subplot(gs[row, 0]); style_ax(ax0)
        ax0.imshow(img, cmap="gray"); ax0.set_xticks([]); ax0.set_yticks([])
        if row == 0:
            ax0.set_title("input (HiRISE/CTX)", color="#e9ebf2", fontsize=9)
        ax0.set_ylabel(f"{label_en}\n({frac*100:.1f}% cone px)", color="#a7aec1", fontsize=8)

        ax1 = fig.add_subplot(gs[row, 1]); style_ax(ax1)
        ax1.imshow(mask, cmap="gray", vmin=0, vmax=1); ax1.set_xticks([]); ax1.set_yticks([])
        if row == 0:
            ax1.set_title("output mask (0/1)", color="#e9ebf2", fontsize=9)

        ax2 = fig.add_subplot(gs[row, 2]); style_ax(ax2)
        ax2.imshow(overlay); ax2.set_xticks([]); ax2.set_yticks([])
        if row == 0:
            ax2.set_title("overlay", color="#e9ebf2", fontsize=9)

    ax_r = fig.add_subplot(gs[0, 4]); style_ax(ax_r)
    regions = global_stats["region_counts"]
    names = list(regions.keys())
    vals = [regions[n] for n in names]
    ax_r.barh(names, vals, color="#5cbcc3")
    ax_r.set_title("full CSV — patches per region (n=13,686)", color="#e9ebf2", fontsize=9)
    ax_r.tick_params(axis="y", labelsize=8)

    ax_s = fig.add_subplot(gs[1, 4]); style_ax(ax_s)
    splits = global_stats["split_counts_bm1"]
    order = ["train", "val", "test", "(미배정)"]
    order_labels = ["train", "val", "test", "unassigned"]
    svals = [splits.get(k, 0) for k in order]
    ax_s.bar(order_labels, svals, color="#e0ac53")
    ax_s.set_title("full CSV — BM-1 split distribution", color="#e9ebf2", fontsize=9)
    ax_s.tick_params(axis="x", labelsize=8)

    ax_l = fig.add_subplot(gs[2, 4]); style_ax(ax_l)
    ax_l.axis("off")
    txt = (
        f"local sample (E084_N12, Isidis Planitia)\n"
        f"  n samples: {local_stats['n_samples']}\n"
        f"  positive (has cone): {local_stats['n_positive_samples']} "
        f"({local_stats['positive_sample_frac']*100:.1f}%)\n"
        f"  mean cone-px frac (positive only): "
        f"{local_stats['mean_pixel_pos_frac_over_positive_samples']*100:.2f}%\n\n"
        f"full-CSV positive rate: {global_stats['positive_frac']*100:.1f}%\n"
        f"(positive rate varies a lot by region --\n"
        f" this sample may be an unusually cone-dense one)"
    )
    ax_l.text(0, 1, txt, color="#e9ebf2", fontsize=9.5, va="top", family="monospace")

    fig.suptitle("ConeQuest EDA -- input/mask structure check (step 1/3)", color="#e9ebf2", fontsize=12, y=0.98)
    fig.savefig(OUT_DIR / "eda_overview.png", dpi=135, bbox_inches="tight", facecolor=fig.get_facecolor())
    print("saved", OUT_DIR / "eda_overview.png")


def main():
    extract_zip()
    global_stats, _ = load_csv_stats()
    local_stats = local_sample_stats()
    examples = pick_examples()
    plot_overview(global_stats, local_stats, examples)

    stats = {"global_csv": global_stats, "local_sample_E084_N12": local_stats}
    with open(OUT_DIR / "eda_stats.json", "w") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)
    print(json.dumps(stats, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

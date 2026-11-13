"""
해커톤 데이터 폴더를 훑어 파일마다 종류를 판단하고, 돌릴 수 있는 학습·보정 단계를 고른다.

    python -m hackathon.intake --drop ../data/hackathon_2026 --name hackathon_2026
    -> ../outputs/hackathon/<name>/manifest.json, intake_report.md

판단 규칙(추정):
  - 지형(dem): .IMG(+LBL), 단일 밴드 실수형 .tif, 고도 .npy
  - 영상·마스크(segmentation): 이름이 같은 영상과 마스크 쌍이 MIN_PAIRS 이상
  - 시계열(table): .csv/.tsv/.txt. 열 이름으로 역할을 추정해 아래 단계를 고른다
        hr + (mr | vo2)                -> hr_regression (심박 -> 대사량 회귀식)
        (mr | vo2) + speed or grade    -> terrain_factor (Pandolf 지형계수 η, 개인 보정 k)
        speed + grade                   -> speed_model (경사별 자율 보행 속도)
        dose                            -> dose (배경 선량률, SPE 배율)
        tank_p                          -> (압력 방식 시뮬레이션 검증용으로 표시만)
  - 경로(vector): features가 있는 .json/.geojson
  - 나머지(pdf, docx ...): 문서로 목록만
"""
from __future__ import annotations

import argparse
import glob
import json
import os

import numpy as np

from hackathon.loaders import read_table, detect_roles, find_image_mask_pairs, IMG_EXT

MIN_PAIRS = 8
OUT_ROOT = "../outputs/hackathon"


def classify(drop: str):
    override = {}
    ov_path = os.path.join(drop, "columns.json")
    if os.path.exists(ov_path):
        override = json.load(open(ov_path, encoding="utf-8"))
    items, pipelines = [], {}

    def add_pipe(name, item):
        pipelines.setdefault(name, []).append(item["path"])

    pairs, img_only, mask_only = find_image_mask_pairs(drop)
    paired = {p for pr in pairs for p in pr}
    for path in sorted(glob.glob(os.path.join(drop, "**", "*"), recursive=True)):
        if os.path.isdir(path) or os.path.basename(path) == "columns.json":
            continue
        rel = os.path.relpath(path, drop)
        ext = os.path.splitext(path)[1].lower()
        it = {"path": rel, "bytes": os.path.getsize(path), "kind": "other"}
        try:
            if ext in (".img",) or (ext == ".lbl" and not os.path.exists(os.path.splitext(path)[0] + ".IMG")
                                     and not os.path.exists(os.path.splitext(path)[0] + ".img")):
                it["kind"] = "dem"
            elif ext == ".lbl":
                it["kind"] = "label"
            elif ext in (".tif", ".tiff") and path not in paired:
                from PIL import Image
                Image.MAX_IMAGE_PIXELS = None
                im = Image.open(path)
                it["kind"] = "dem" if im.mode in ("F", "I", "I;16", "I;16S", "I;32") and len(im.getbands()) == 1 else "image"
                it["mode"], it["size"] = im.mode, im.size
            elif ext == ".npy":
                arr = np.load(path, mmap_mode="r")
                it["kind"] = "dem" if arr.ndim == 2 and arr.dtype.kind == "f" else "array"
                it["shape"] = list(arr.shape)
            elif ext in IMG_EXT:
                it["kind"] = "seg_pair" if path in paired else "image"
            elif ext in (".csv", ".tsv", ".txt"):
                cols, kinds = read_table(path, max_rows=5000)
                n = len(next(iter(cols.values()))) if cols else 0
                roles = detect_roles(list(cols), kinds, override.get(rel) or override.get(os.path.basename(path)))
                it.update(kind="table", rows=n, columns=list(cols), roles=roles)
                r = set(roles)
                if "hr" in r and ({"mr", "vo2"} & r):
                    add_pipe("hr_regression", it)
                if ({"mr", "vo2"} & r) and ({"speed", "grade"} & r):
                    add_pipe("terrain_factor", it)
                if {"speed", "grade"} <= r:
                    add_pipe("speed_model", it)
                if "dose" in r:
                    add_pipe("dose", it)
                if "tank_p" in r:
                    add_pipe("tank_pressure_check", it)
            elif ext in (".json", ".geojson"):
                js = json.load(open(path, encoding="utf-8"))
                it["kind"] = "vector" if isinstance(js, dict) and "features" in js else "json"
            elif ext in (".pdf", ".docx", ".pptx", ".md", ".html"):
                it["kind"] = "document"
        except Exception as e:                       # 읽기 실패도 보고서에 남긴다
            it["kind"], it["error"] = "unreadable", f"{type(e).__name__}: {e}"
        if it["kind"] == "dem":
            add_pipe("dem_walkback", it)
        items.append(it)
    if len(pairs) >= MIN_PAIRS:
        pipelines["segmentation"] = [os.path.relpath(drop, drop)]
    seg = {"pairs": len(pairs), "images_without_mask": len(img_only), "masks_without_image": len(mask_only),
           "example": [os.path.relpath(p, drop) for p in pairs[0]] if pairs else None}
    return items, pipelines, seg


PIPE_DESC = {
    "hr_regression": "심박 → 대사량 회귀식 다시 맞추기 (calibrate_metabolic)",
    "terrain_factor": "지면별 지형계수 η, 개인 보정 k (calibrate_metabolic)",
    "speed_model": "경사별 자율 보행 속도식 (calibrate_metabolic)",
    "dose": "배경 선량률, SPE 배율 (calibrate_dose)",
    "dem_walkback": "새 지형에서 귀환 반경 계산 (dem_walkback)",
    "segmentation": "지형 분할 U-Net 미세조정 (finetune_segmentation)",
    "tank_pressure_check": "탱크 압력 자료: 압력 방식 시뮬레이션 검증에 쓸 수 있음 (자동 단계 없음)",
}


def write_report(out_dir, drop, items, pipelines, seg):
    os.makedirs(out_dir, exist_ok=True)
    manifest = {"drop": os.path.abspath(drop), "items": items, "pipelines": pipelines, "segmentation": seg}
    with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1, default=str)
    by_kind = {}
    for it in items:
        by_kind.setdefault(it["kind"], []).append(it)
    L = [f"# 데이터 접수 보고서", "", f"- 폴더: `{drop}`", f"- 파일 {len(items)}개", ""]
    L += ["## 종류별", "", "| 종류 | 개수 | 예시 |", "|---|---|---|"]
    for k, its in sorted(by_kind.items()):
        L.append(f"| {k} | {len(its)} | `{its[0]['path']}` |")
    L += ["", "## 돌릴 수 있는 단계", ""]
    if not pipelines:
        L.append("- 자동으로 고를 수 있는 단계가 없습니다. 열 이름이 달라서일 수 있습니다: `columns.json`으로 지정하세요.")
    for p, files in pipelines.items():
        L.append(f"- **{p}**: {PIPE_DESC.get(p, '')} ← " + ", ".join(f"`{x}`" for x in files[:4]) + (" …" if len(files) > 4 else ""))
    tables = [it for it in items if it["kind"] == "table"]
    if tables:
        L += ["", "## 표 데이터: 열 역할 추정", "", "열 이름으로 추정했습니다. 틀리면 데이터 폴더에 `columns.json`을 두고 다시 실행하세요.", ""]
        for it in tables:
            rs = ", ".join(f"{r}=`{v['column']}`({v['unit']})" for r, v in it["roles"].items()) or "(추정된 역할 없음)"
            L.append(f"- `{it['path']}` ({it['rows']}행): {rs}")
    if seg["pairs"] or seg["images_without_mask"]:
        L += ["", "## 영상·마스크", "", f"- 쌍 {seg['pairs']}개, 마스크 없는 영상 {seg['images_without_mask']}개, 영상 없는 마스크 {seg['masks_without_image']}개"]
        if seg["pairs"] < MIN_PAIRS:
            L.append(f"- 쌍이 {MIN_PAIRS}개 미만이라 학습 단계는 고르지 않았습니다.")
    bad = [it for it in items if it["kind"] == "unreadable"]
    if bad:
        L += ["", "## 읽지 못한 파일", ""] + [f"- `{it['path']}`: {it['error']}" for it in bad]
    with open(os.path.join(out_dir, "intake_report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    return manifest


def main(drop, name):
    items, pipelines, seg = classify(drop)
    out_dir = os.path.join(OUT_ROOT, name)
    m = write_report(out_dir, drop, items, pipelines, seg)
    print(f"파일 {len(items)}개, 단계 {list(pipelines)} -> {out_dir}/intake_report.md")
    return m


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--drop", default="../data/hackathon_2026")
    ap.add_argument("--name", default="hackathon_2026")
    a = ap.parse_args()
    main(a.drop, a.name)

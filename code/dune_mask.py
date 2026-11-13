"""
Bagnold 모래언덕(활동 사구) 후보 영역을 HiRISE 정사영상 밝기로 만든다.

왜: Richmond, Potter & Santee 2015(J Sport Hum Perf 3(3))는 모래 위 보행의 지형계수를
η = 1.5 + 1.3/V² 로 권장한다(0.92 m/s에서 약 3.0). 데모 지도 남쪽의 Bagnold 사구는 현무암질 모래라
HiRISE RED 영상에서 주변 표토보다 확실히 어둡다(Bridges et al. 2017 등 Bagnold 사구 연구에서 쓰는 특징).

방법(추정, 측정값 아님):
  1. 정사영상을 4 m로 디코드해 데모 격자(10 m 칸)에 상자 평균으로 맞춘다.
  2. 3x3 칸 평균으로 잡음을 줄인 뒤 Otsu 문턱값을 두 번 적용한다. 첫 번째는 밝은 표토와 어두운 곳
     (사구 + Murray 암반)을 나누고, 두 번째는 어두운 쪽 안에서 가장 어두운 사구를 가른다.
  3. 면적이 MIN_BLOB_CELLS보다 작은 덩어리(크레이터 벽 그늘 등)는 버린다.
한계: 그늘진 급사면, 어두운 암반이 섞일 수 있고 얇은 모래 덮개는 놓친다. 현장 확인 전에는 "후보"다.

실행: python dune_mask.py  -> outputs/demo/dune_mask.npy, dune_mask_preview.png
"""
import numpy as np
from PIL import Image
from scipy import ndimage

from mars_walkback import CROP_LINES, CROP_SAMPLES

ORTHO = "../data/hirise_dtm/ESP_018854_1755_RED_C_01_ORTHO.JP2"
OUT_DIR = "../outputs/demo"
DECODE_M = 4
MIN_BLOB_CELLS = 30          # 30칸(10 m 격자면 0.003 km²) 미만 덩어리는 사구로 보지 않음 (설계 가정; 이전 주석의 0.3 km²는 오기)


def otsu(x):
    hist, edges = np.histogram(x, bins=256)
    p = hist / hist.sum()
    w = np.cumsum(p); mu = np.cumsum(p * edges[:-1]); mt = mu[-1]
    sb = (mt * w - mu) ** 2 / np.maximum(w * (1 - w), 1e-12)
    return edges[np.argmax(sb)]


def decode_ortho_4m(path):
    """JPEG 2000 정사영상을 4 m(1/4)로 디코드. 일부 파일은 1/4 단계가 깨져 있어 1/2로 풀고 2배 줄인다
    (Jezero ESP_045994_1985_RED_C: reduce=2에서 "broken data stream")."""
    Image.MAX_IMAGE_PIXELS = None
    try:
        im = Image.open(path); im.reduce = 2
        return np.asarray(im.convert("L"))
    except OSError:
        im = Image.open(path); im.reduce = 1
        a = im.convert("L")
        return np.asarray(a.resize((a.size[0] // 2, a.size[1] // 2), Image.BOX))


def build(shape, ortho=ORTHO, crop_lines=CROP_LINES, crop_samples=CROP_SAMPLES):
    rows, cols = shape
    full = decode_ortho_4m(ortho)
    l0, l1 = (v // DECODE_M for v in crop_lines)
    s0, s1 = (v // DECODE_M for v in crop_samples)
    g = full[l0:l1, s0:s1].astype(np.float32)
    valid = (g > 0).astype(np.float32)
    # 상자 평균으로 격자에 맞춤 (NoData 제외)
    gs = np.asarray(Image.fromarray(g * valid).resize((cols, rows), Image.BOX), np.float32)
    vs = np.asarray(Image.fromarray(valid).resize((cols, rows), Image.BOX), np.float32)
    bright = np.where(vs > 0.5, gs / np.maximum(vs, 1e-6), np.nan)
    sm = ndimage.uniform_filter(np.nan_to_num(bright, nan=np.nanmedian(bright)), 3)
    ok = np.isfinite(bright)
    thr1 = otsu(sm[ok])
    thr = otsu(sm[ok & (sm < thr1)])
    dark = ok & (sm < thr)
    lab, n = ndimage.label(dark)
    sizes = ndimage.sum(dark, lab, range(1, n + 1))
    keep = np.isin(lab, 1 + np.nonzero(sizes >= MIN_BLOB_CELLS)[0])
    return keep, bright, float(thr)


if __name__ == "__main__":
    from spe_walkback import load_scene
    h, valid, *_ = load_scene()
    mask, bright, thr = build(h.shape)
    np.save(f"{OUT_DIR}/dune_mask.npy", mask)
    km2 = mask.sum() * 1e-4
    print(f"Otsu 문턱 {thr:.1f}, 사구 후보 {mask.sum()} 칸 = {km2:.2f} km² (유효 {valid.sum() * 1e-4:.2f} km²)")
    rgb = np.dstack([np.nan_to_num(bright / np.nanmax(bright))] * 3)
    rgb[mask] = rgb[mask] * 0.4 + np.array([0.2, 0.5, 1.0]) * 0.6
    Image.fromarray((rgb * 255).astype(np.uint8)).save(f"{OUT_DIR}/dune_mask_preview.png")

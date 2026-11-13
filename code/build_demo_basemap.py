"""
데모 지도 바탕에 깔 HiRISE 정사영상을 만든다.

ESP_018854_1755_RED_C_01_ORTHO.JP2는 DTM(DTEEC_018854_1755_018920_1755_U01)과 같은 투영·같은 격자
(15040 x 7075, 1.0118 m/px, 같은 projection offset)라서, mars_walkback의 CROP_LINES/CROP_SAMPLES를
그대로 잘라 쓰면 데모의 10 m 칸과 화소 단위로 맞는다.

RED 밴드(중심 700 nm) 흑백 영상이다. 화면에서 화성처럼 보이도록 밝기를 화성 표토 색조로 매핑한
것은 표시용 가색(false color)이며 실제 색 측정값이 아니다.

받기: https://hirise-pds.lpl.arizona.edu/PDS/DTM/ESP/ORB_018800_018899/ESP_018854_1755_ESP_018920_1755/
실행: python build_demo_basemap.py  -> outputs/demo/basemap.jpg
"""
import numpy as np
from PIL import Image

from mars_walkback import CROP_LINES, CROP_SAMPLES

ORTHO = "../data/hirise_dtm/ESP_018854_1755_RED_C_01_ORTHO.JP2"
OUT = "../outputs/demo/basemap.jpg"
OUT_M_PER_PX = 4          # 1 m -> 4 m (화면 폭 800 px에서 레티나 해상도 정도)
# 어두운 곳 -> 밝은 곳: 그늘진 현무암질 모래 ~ 먼지 덮인 밝은 표토 (표시용 색조)
TINT = np.array([[22, 14, 10], [92, 52, 32], [168, 104, 64], [222, 170, 120], [246, 222, 188]], float)


def main():
    Image.MAX_IMAGE_PIXELS = None
    im = Image.open(ORTHO)
    im.reduce = 2                          # JPEG2000 해상도 단계: 1/4 크기(4 m)로 바로 디코드
    full = np.asarray(im.convert("L"))
    l0, l1 = (v // OUT_M_PER_PX for v in CROP_LINES)
    s0, s1 = (v // OUT_M_PER_PX for v in CROP_SAMPLES)
    g = full[l0:l1, s0:s1].astype(float)
    print(f"원본 {im.size}, 1/{OUT_M_PER_PX} 디코드 {full.shape}, 자른 영역 {g.shape}")

    valid = g > 0                          # 0 = NoData
    lo, hi = np.percentile(g[valid], [0.5, 99.5])
    t = np.clip((g - lo) / (hi - lo), 0, 1) ** 0.9
    pos = t * (len(TINT) - 1)
    i0 = np.clip(pos.astype(int), 0, len(TINT) - 2)
    f = (pos - i0)[..., None]
    rgb = TINT[i0] * (1 - f) + TINT[i0 + 1] * f
    rgb[~valid] = 0
    Image.fromarray(rgb.astype(np.uint8)).save(OUT, quality=82, optimize=True, progressive=True)
    print(f"saved {OUT} {rgb.shape[1]}x{rgb.shape[0]}, 밝기 범위 {lo:.0f}~{hi:.0f}")


if __name__ == "__main__":
    main()

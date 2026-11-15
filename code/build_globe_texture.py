"""
3D 지구본 텍스처: NASA/JPL Mars Trek의 Viking MDIM 2.1 컬러 모자이크(실제 색에 가까운 전역 영상)를
WMTS 2단계(8 x 4 타일, 256 px)로 받아 2048 x 1024 등장방형 한 장으로 붙인다.
    python build_globe_texture.py   ->  global_map.json 의 image/source 를 바꿈 (핀 좌표는 그대로)
타일: https://trek.nasa.gov/tiles/Mars/EQ/Mars_Viking_MDIM21_ClrMosaic_global_232m/1.0.0/default/default028mm/{z}/{row}/{col}.jpg
"""
import base64, io, json, os, subprocess
from PIL import Image

LAYER = "Mars_Viking_MDIM21_ClrMosaic_global_232m"
URL = "https://trek.nasa.gov/tiles/Mars/EQ/" + LAYER + "/1.0.0/default/default028mm/{z}/{r}/{c}.jpg"
Z, COLS, ROWS, T = 2, 8, 4, 256
CACHE = "../data/globe_tiles"

def tile(r, c):
    p = f"{CACHE}/{Z}_{r}_{c}.jpg"
    if not os.path.exists(p):
        os.makedirs(CACHE, exist_ok=True)
        subprocess.run(["curl", "-s", "-f", "-A", "Mozilla/5.0", "--max-time", "60", "-o", p, URL.format(z=Z, r=r, c=c)], check=True)
    return Image.open(p).convert("RGB")

img = Image.new("RGB", (COLS * T, ROWS * T))
for r in range(ROWS):
    for c in range(COLS):
        img.paste(tile(r, c), (c * T, r * T))
buf = io.BytesIO(); img.save(buf, "JPEG", quality=84, optimize=True, progressive=True)
w = json.load(open("global_map.json"))
w["image"] = "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
w["width"], w["height"] = img.size
w["source"] = "NASA/JPL Mars Trek · Viking MDIM 2.1 colour mosaic"
json.dump(w, open("global_map.json", "w"))
print("saved", img.size, f"{len(buf.getvalue()) / 1e6:.2f} MB")

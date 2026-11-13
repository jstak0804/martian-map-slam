"""
demo_template.html + build_demo_data.py 출력물 -> 파일 하나짜리 데모 demo/gale-eva-walkback-demo.html
(2026-11-12 계획 J2: 이전 출력 경로 ../reports/18-eva-walkback-demo.html에서 demo/로 바꿈)

실행: python build_demo_data.py && python build_demo_basemap.py && python build_demo_html.py
"""
import base64

OUT = "../demo/gale-eva-walkback-demo.html"


def main():
    html = open("demo_template.html", encoding="utf-8").read()
    meta = open("../outputs/demo/demo_meta.json", encoding="utf-8").read()
    data = base64.b64encode(open("../outputs/demo/demo_data.bin.gz", "rb").read()).decode()
    shade = "data:image/png;base64," + base64.b64encode(open("../outputs/demo/hillshade.png", "rb").read()).decode()
    ortho = "data:image/jpeg;base64," + base64.b64encode(open("../outputs/demo/basemap.jpg", "rb").read()).decode()
    for key, val in (("__META__", meta.replace("</", "<\\/")), ("__DATA__", data), ("__SHADE__", shade),
                     ("__ORTHO__", ortho)):
        assert html.count(key) == 1, key
        html = html.replace(key, val)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"saved {OUT} ({len(html.encode()) / 1e6:.2f} MB)")


if __name__ == "__main__":
    main()

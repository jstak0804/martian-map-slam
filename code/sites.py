"""
데모에 넣는 지역 설정. Gale은 build_demo_data.py(기존, 미리 계산한 귀환 트리 포함)로 만들고,
나머지 지역은 build_site_data.py가 이 설정만 보고 만든다(귀환 트리는 브라우저가 계산).

새 지역을 넣으려면: HiRISE DTM(.IMG)과 같은 관측의 RED_C 정사영상(.JP2)을 받고 아래에 항목을 더한다.
  - crop_lines / crop_samples: 1 m 화소 범위(10 m 칸으로 묶임). 거점과 장애물이 함께 들어오게.
  - base: 거점 위경도(실제 착륙 지점 등). goal: 예시 목적지 위경도 또는 auto(귀환 산소 150~230 g 중
    직선 대비 귀환 산소가 가장 많이 드는 칸 = 장애물을 가장 많이 돌아가는 곳).
  - DTM 투영 값은 라벨에서 자동으로 읽는다.
"""

DEMO_SITES = ["jezero", "aram"]      # 데모에 넣는 순서 (Gale 다음)

SITES = {
    "jezero": {
        "name": "Jezero 크레이터 삼각주",
        "short": "Jezero (Perseverance)",
        "dtm": "../data/hirise_jezero/DTEEC_045994_1985_046060_1985_U01.IMG",
        "ortho": "../data/hirise_jezero/ESP_045994_1985_RED_C_01_ORTHO.JP2",
        "crop_lines": (0, 7000),            # 삼각주 앞 절벽이 최대한 들어오게 (장애물 비율이 가장 높은 7 km 구간)
        "crop_samples": (0, 6673),
        "base": {"lat": 18.4447, "lon": 77.4508, "name": "Perseverance 착륙지 (Octavia E. Butler Landing)"},
        "goal": {"auto": "detour", "name": "절벽을 돌아가야 하는 곳 (자동으로 고른 예시 목적지)"},
        "dunes": False,                      # 밝기로 뽑으면 사구가 아니라 삼각주 절벽 그늘이 잡혀 끔
        "description_en": "Delta-front scarps (tens of metres, steep) to the north-west and layered terrain and craters to the south. Walking around the scarps makes the way home much longer than the straight line.",
        "description": "북서쪽 삼각주 앞 절벽(수십 m 급경사)과 남쪽의 층진 지형·크레이터. 절벽을 돌아가야 해서 귀환 길이 직선보다 훨씬 길어진다.",
        "source": "HiRISE DTM DTEEC_045994_1985_046060_1985_U01 (Mars 2020 착륙 후보지 관측), 정사영상 ESP_045994_1985_RED_C",
    },
    "aram": {
        "name": "Aram Chaos 혼돈 지형",
        "short": "Aram Chaos (가상 거점)",
        "dtm": "../data/hirise_aram/DTEEC_054753_1825_055452_1825_A01.IMG",
        "ortho": "../data/hirise_aram/ESP_054753_1825_RED_C_01_ORTHO.JP2",
        "crop_lines": (400, 7400),           # 장애물 비율이 가장 높은 7 km 구간
        "crop_samples": (0, 5800),
        "base": {"auto": "flat", "name": "평탄한 바닥 (자동으로 고른 가상 거점)"},
        "goal": {"auto": "detour", "name": "블록을 돌아가야 하는 곳 (자동으로 고른 예시 목적지)"},
        "dunes": False,                      # 어두운 곳이 사구가 아니라 급사면 그늘이라 끔
        "description_en": "Chaotic terrain packed with collapsed crustal blocks and hummocks: 19% of cells over 20°, 74% high fall risk on the 1 m DTM. You have to find corridors between blocks to get home.",
        "description": "무너진 지각 블록과 언덕(hummock)이 빽빽한 혼돈 지형. 경사 20° 넘는 칸 19%, 1 m 지형의 넘어짐 위험 '높음' 74%. 블록 사이 통로를 찾아 돌아와야 한다.",
        "source": "HiRISE DTM DTEEC_054753_1825_055452_1825_A01, 정사영상 ESP_054753_1825_RED_C",
    },
    "columbia": {          # Gale과 장애물 수준이 비슷해(넘어짐 높음 8%) 데모에서는 뺌. python build_site_data.py columbia 로 만들 수 있음
        "name": "Gusev 크레이터 Columbia Hills",
        "short": "Columbia Hills (Spirit)",
        "dtm": "../data/hirise_columbia/DTEEC_001513_1655_001777_1650_U01.IMG",
        "ortho": "../data/hirise_columbia/PSP_001513_1655_RED_C_01_ORTHO.JP2",
        "crop_lines": (2000, 9000),
        "crop_samples": (0, 6524),
        "base": {"lat": -14.5684, "lon": 175.4726, "name": "Spirit 착륙지 (Columbia Memorial Station)"},
        "goal": {"lat": -14.643, "lon": 175.526, "name": "Home Plate 부근 (근사 좌표)"},
        "description": "평원 곳곳의 작은 크레이터와 동남쪽 Husband Hill 언덕군(급사면, 바위). 언덕을 넘지 않고 돌아가는 길을 찾아야 한다.",
        "source": "HiRISE DTM DTEEC_001513_1655_001777_1650_U01, 정사영상 PSP_001513_1655_RED_C",
    },
}

GALE = {
    "name": "Gale 크레이터", "short": "Gale (Curiosity)",
    "base_name": "Curiosity 착륙지 (Bradbury Landing)", "goal_name": "sol 1282 지점",
    "description_en": "Gentle plains and the Bagnold dunes from the landing site to the foot of Mt. Sharp. The easiest of the three, used as the baseline.",
    "description": "착륙지에서 Mt. Sharp 기슭까지 완만한 평원과 Bagnold 모래언덕. 세 지역 중 가장 걷기 쉬운 기준 지역.",
    "source": "HiRISE DTM DTEEC_018854_1755_018920_1755_U01, 정사영상 ESP_018854_1755_RED_C, Curiosity 주행 경로(MMGIS)",
}

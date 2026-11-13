"""
실제 화성 지형(데모의 지역 자료) 전체를 탐사하는 SLAM 시뮬레이션 + 배속 영상.

    python slam_site_exploration.py aram        # 또는 jezero, gale
    -> ../outputs/slam_sites/<id>/ slam_<id>.mp4, slam_<id>_final.png, slam_<id>_stats.json

exploration_slam_sim.py(44 m 합성 지형, 0.2 m 칸)와 같은 모델을 km 규모(HiRISE 10 m 칸)로 키운 것이다.
  - 정지-스캔 카메라: 마스트 높이에서 레이캐스팅으로 보이는 지형만 관측(지형 가림),
    깊이 오차는 거리 제곱에 비례(스테레오), 위험도 측정에도 잡음.
  - 탐사: 지도 전체의 프런티어(아는 땅과 모르는 땅의 경계) 중 "새로 볼 수 있는 넓이 ÷ 가는 비용"이 가장 큰 곳으로.
    경로는 지금까지 알게 된 땅 위로만 짜고(경사 20° 넘는 칸 금지), 위험한 칸은 비용을 키워 피한다.
    가는 길에 STOP_EVERY_M마다 멈춰 스캔한다(화성 로버의 이동-정지-스캔 운용).
  - 위치 추정 세 가지를 나란히:
      참값(Oracle)  : 완벽한 위치 — 비교 기준
      VO만          : 구간마다 거리 오차(VO_SCALE_SIGMA)와 방향 오차가 누적 (MER VO는 거리의 2% 이내로 보고됨)
      SLAM          : VO + 루프 클로저. 예전에 지도로 만든 곳을 LOOP_MIN_OVERLAP 칸 이상 다시 보면
                      지도-지도 정합으로 위치를 바로잡는다(잔차 LOOP_RESIDUAL_M). 마지막 지도는 클로저 사이 구간의
                      위치를 선형으로 나눠 고친 값으로 다시 만든다(간단한 포즈 그래프 근사).
  - 평가: 관측 범위(커버리지), 고위험지대 IoU(참 위험도 대비), 고도 RMSE, 위치 오차(최종·최대).

참 위험도 = 0.5·(10 m 경사 / 20°) + 0.5·(1 m 지형 넘어짐 위험 등급 / 2), 경사 20° 초과는 통행 불가 — 데모와 같은 자료.
가정: 카메라·VO 값은 화성 로버급 운용을 흉내 낸 설계값이며 특정 로버의 사양이 아니다.
"""
from __future__ import annotations

import gzip
import json
import os
import sys
import time

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.colors import LinearSegmentedColormap
from PIL import Image
from scipy.ndimage import uniform_filter, binary_dilation, binary_closing
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra

# ---------------------------------------------------------------- 설정 (설계값)
MAST_M = 2.0               # 카메라 높이
RANGE_M = 250.0            # 스캔 최대 거리
N_BEARINGS = 180           # 360° 스캔 방향 수 (2°)
STEREO_BASE_M = 0.42       # 스테레오 베이스라인 (Navcam급)
DEPTH_K = 24000.0          # depth_std = r² / (B·K): 100 m에서 약 1 m
RISK_NOISE = 0.05
STOP_EVERY_M = 200.0       # 이동 중 정지-스캔 간격
DRIVE_M_PER_H = 100.0      # 미션 시간 환산용 주행 속도
SCAN_MIN = 10.0            # 정지-스캔 1회 시간(분)
VO_SCALE_SIGMA = 0.015     # 구간마다 거리 오차 (1.5%)
VO_HEAD_SIGMA_DEG = 0.4    # 구간마다 방향 오차 (누적, 랜덤워크)
LOOP_MIN_OVERLAP = 150     # 루프 클로저: 다시 본 옛 지도 칸 수
LOOP_MIN_GAP = 8           # 몇 정지 이상 지난 지도여야 "다시 봤다"로 침
LOOP_RESIDUAL_M = 6.0      # 정합 후 남는 위치 오차
LOOP_RESIDUAL_DEG = 0.3    # 정합 후 남는 방향 오차
COVER_TARGET = 0.90        # 유효 지형의 이 비율을 보면 끝 (그 뒤는 골짜기 틈을 보려고 정지만 수백 번 늘어남)
MAX_STOPS = 2500
HIGH_RISK = 0.55
SEED = 7
OFF8 = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]
RISK_CMAP = LinearSegmentedColormap.from_list("risk", [(0.11, 0.42, 0.45), (0.85, 0.75, 0.25), (0.75, 0.22, 0.18)])


def load_site(site_id):
    if site_id == "gale":
        d, meta_p, data_p, base_p = "../outputs/demo", "../outputs/demo/demo_meta.json", "../outputs/demo/demo_data.bin.gz", "../outputs/demo/basemap.jpg"
    else:
        d = f"../outputs/demo/sites/{site_id}"
        meta_p, data_p, base_p = f"{d}/meta.json", f"{d}/data.bin.gz", f"{d}/basemap.jpg"
    meta = json.load(open(meta_p, encoding="utf-8"))
    raw = gzip.decompress(open(data_p, "rb").read())
    v = lambda n, dt: np.frombuffer(raw[meta["layout"][n][0]: meta["layout"][n][0] + meta["layout"][n][1]], dt).reshape(meta["rows"], meta["cols"])
    fl, cls = v("flags", np.uint8), v("cls", np.uint8)
    valid = (fl & 1) > 0
    h = meta["h_min"] + v("h", "<u2").astype(np.float64) * meta["h_step"]
    h[~valid] = np.nan
    cell = meta["cell_m"]
    hf = np.where(valid, h, np.nanmean(h))
    gy, gx = np.gradient(hf, cell)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    passable = (fl & 8) > 0
    risk = np.clip(0.5 * slope / 20 + 0.5 * cls / 2, 0, 1)
    risk[~valid] = np.nan
    basemap = np.asarray(Image.open(base_p).convert("RGB").resize((meta["cols"], meta["rows"]), Image.BILINEAR))
    name = {"gale": "Gale crater (Curiosity landing site)", "jezero": "Jezero crater delta (Perseverance landing site)",
            "aram": "Aram Chaos (virtual base)", "columbia": "Columbia Hills (Spirit landing site)"}.get(site_id, site_id)
    return dict(meta=meta, h=h, hf=hf, valid=valid, passable=passable, risk=risk, cell=cell, basemap=basemap, name=name,
                base=tuple(meta["base"]))


class Explorer:
    def __init__(self, S, seed=SEED):
        self.S = S
        self.rng = np.random.default_rng(seed)
        R, C = S["h"].shape
        self.R, self.C = R, C
        self.cell = S["cell"]
        self.known = np.zeros((R, C), bool)          # 관측한 칸 (참좌표, 의사결정용)
        self.stop_of = np.full((R, C), -1, np.int32)
        self.visited = np.zeros((R, C), bool)  # 그 칸을 처음 본 정지 번호 (루프 클로저 판단)
        # 정지 기록: 참 위치, VO 위치, SLAM 위치, 관측(칸, 측정 고도, 측정 위험도, 가중치)
        self.true_pos, self.vo_pos, self.slam_pos = [], [], []
        self.obs = []
        self.closures = []
        self.dist_m = [0.0]
        self.scan_area = []
        self._build_graph()
        # 레이 표본 (방향 × 거리)
        n_step = int(RANGE_M / (0.5 * self.cell))
        self.r_m = (np.arange(1, n_step + 1) * 0.5 * self.cell)
        th = np.radians(np.linspace(0, 360, N_BEARINGS, endpoint=False))
        self.dx, self.dy = np.sin(th), -np.cos(th)

    def _build_graph(self):
        S = self.S; R, C = self.R, self.C
        idx = np.arange(R * C).reshape(R, C)
        src, dst, w = [], [], []
        for dx, dy in OFF8:
            ys, ye = max(0, -dy), R - max(0, dy); xs, xe = max(0, -dx), C - max(0, dx)
            a = (slice(ys, ye), slice(xs, xe)); b = (slice(ys + dy, ye + dy), slice(xs + dx, xe + dx))
            ok = S["passable"][a] & S["passable"][b]
            d = np.hypot(dx, dy) * self.cell
            rk = 0.5 * (np.nan_to_num(S["risk"][a]) + np.nan_to_num(S["risk"][b]))
            src.append(idx[a][ok]); dst.append(idx[b][ok]); w.append((d * (1 + 4 * rk))[ok])
        self.G = csr_matrix((np.concatenate(w), (np.concatenate(src), np.concatenate(dst))), shape=(R * C, R * C))

    def scan(self, pos):
        """참 위치 pos(x, y 칸)에서 360° 스캔. 보이는 칸 목록과 측정값."""
        S = self.S
        x = pos[0] + self.dx[:, None] * self.r_m[None, :] / self.cell
        y = pos[1] + self.dy[:, None] * self.r_m[None, :] / self.cell
        inside = (x >= 0) & (y >= 0) & (x < self.C - 1) & (y < self.R - 1)
        xi, yi = np.clip(x, 0, self.C - 1.001), np.clip(y, 0, self.R - 1.001)
        x0, y0 = xi.astype(int), yi.astype(int); fx, fy = xi - x0, yi - y0
        hf = S["hf"]
        th = (hf[y0, x0] * (1 - fx) * (1 - fy) + hf[y0, x0 + 1] * fx * (1 - fy) + hf[y0 + 1, x0] * (1 - fx) * fy + hf[y0 + 1, x0 + 1] * fx * fy)
        eye = hf[int(pos[1]), int(pos[0])] + MAST_M
        elev = (th - eye) / self.r_m[None, :]
        elev = np.where(inside, elev, -np.inf)
        prev_max = np.maximum.accumulate(np.concatenate([np.full((N_BEARINGS, 1), -np.inf), elev[:, :-1]], axis=1), axis=1)
        vis = inside & (elev >= prev_max)
        cx, cy = np.rint(x[vis]).astype(int), np.rint(y[vis]).astype(int)
        rr = np.broadcast_to(self.r_m[None, :], vis.shape)[vis]
        cx, cy = np.clip(cx, 0, self.C - 1), np.clip(cy, 0, self.R - 1)
        keep = S["valid"][cy, cx]
        cx, cy, rr = cx[keep], cy[keep], rr[keep]
        # 같은 칸을 여러 레이가 보면 가장 가까운 것만
        lin = cy * self.C + cx
        order = np.lexsort((rr, lin)); lin, rr = lin[order], rr[order]
        first = np.r_[True, lin[1:] != lin[:-1]]
        lin, rr = lin[first], rr[first]
        std = np.maximum(0.05, rr ** 2 / (STEREO_BASE_M * DEPTH_K))
        mh = S["hf"].ravel()[lin] + self.rng.normal(0, std)
        mr = np.clip(np.nan_to_num(S["risk"].ravel()[lin]) + self.rng.normal(0, RISK_NOISE, len(lin)), 0, 1)
        return lin, mh, mr, 1 / std ** 2

    def _still_frontier(self, cell):
        y, x = divmod(int(cell), self.C)
        y0, y1, x0, x1 = max(0, y - 3), y + 4, max(0, x - 3), x + 4
        return bool((self.S["valid"][y0:y1, x0:x1] & ~self.known[y0:y1, x0:x1]).any())

    def pick_target(self, cur):
        """프런티어 중 (새로 볼 넓이) ÷ (가는 비용 + 상수)가 가장 큰 곳. 아는 땅으로만 이동."""
        S = self.S
        unknown = S["valid"] & ~self.known
        # 레이로 본 칸은 듬성듬성하므로 이동 계획용 지도는 1~2칸 틈을 메워 쓴다(관측 사이 보간)
        knav = self.known | binary_closing(self.known, structure=np.ones((3, 3)), iterations=2)
        k_pass = knav & S["passable"]
        frontier = k_pass & binary_dilation(unknown, structure=np.ones((3, 3))) & ~self.visited   # 이미 스캔한 자리 근처는 빼기

        if not frontier.any():
            return None, None
        nodes = np.flatnonzero(k_pass.ravel())
        pos_in = np.full(self.R * self.C, -1, np.int64); pos_in[nodes] = np.arange(len(nodes))
        sub = self.G[nodes][:, nodes]
        start = pos_in[cur]
        if start < 0:
            return None, None
        dist, pred = dijkstra(sub, directed=True, indices=start, return_predecessors=True)
        win = int(2 * RANGE_M / self.cell) | 1
        gain = uniform_filter(unknown.astype(np.float32), size=win) * win * win     # 그 근처 모르는 칸 수
        fr = np.flatnonzero(frontier.ravel())
        fd = dist[pos_in[fr]]
        ok = np.isfinite(fd)
        if not ok.any():
            return None, None
        fr, fd = fr[ok], fd[ok]
        util = gain.ravel()[fr] / (fd + 300.0)
        best = fr[np.argmax(util)]
        # 경로 복원 (전체 칸 번호)
        path, j = [], pos_in[best]
        while j != -9999 and j >= 0:
            path.append(nodes[j]); j = pred[j]
        return best, path[::-1]

    def run(self, log_every=50):
        S = self.S
        bx, by = S["base"]
        true = np.array([bx + 0.5, by + 0.5]); vo = true.copy(); slam = true.copy()
        head_bias = 0.0            # VO가 쌓은 방향 오차 (rad)
        slam_head_off = 0.0        # SLAM이 루프 클로저로 바로잡은 방향 (SLAM 방향 오차 = head_bias - slam_head_off)
        valid_n = S["valid"].sum()
        last_closure = 0
        plan = None
        self.replans = 0
        t0 = time.time()
        while len(self.true_pos) < MAX_STOPS:
            # --- 정지 & 스캔 ---
            i = len(self.true_pos)
            self.true_pos.append(true.copy()); self.vo_pos.append(vo.copy()); self.slam_pos.append(slam.copy())
            lin, mh, mr, w = self.scan(true)
            self.obs.append((lin, mh, mr, w))
            old = self.stop_of.ravel()[lin]
            revisit = ((old >= 0) & (old <= i - LOOP_MIN_GAP)).sum()
            if revisit >= LOOP_MIN_OVERLAP and np.linalg.norm(slam - true) * self.cell > LOOP_RESIDUAL_M:
                new_slam = true + self.rng.normal(0, LOOP_RESIDUAL_M / self.cell, 2)
                self.closures.append((i, last_closure, (new_slam - slam).copy()))
                slam = new_slam; self.slam_pos[-1] = slam.copy(); last_closure = i
                slam_head_off = head_bias - self.rng.normal(0, np.radians(LOOP_RESIDUAL_DEG))   # 방향도 지도 정합으로 바로잡음
            newly = self.stop_of.ravel()[lin] < 0
            self.stop_of.ravel()[lin[newly]] = i
            self.known.ravel()[lin] = True
            self.known[int(true[1]), int(true[0])] = True
            cy_, cx_ = int(true[1]), int(true[0])
            self.visited[max(0, cy_ - 3):cy_ + 4, max(0, cx_ - 3):cx_ + 4] = True    # 스캔한 자리 반경 30 m
            self.scan_area.append(lin)
            cover = (self.known & S["valid"]).sum() / valid_n
            if log_every and i % log_every == 0:
                print(f"  정지 {i}: 커버리지 {cover * 100:.1f}%, 이동 {self.dist_m[-1] / 1000:.1f} km, "
                      f"VO 오차 {np.linalg.norm(vo - true) * self.cell:.0f} m, SLAM 오차 {np.linalg.norm(slam - true) * self.cell:.0f} m, "
                      f"클로저 {len(self.closures)}, {time.time() - t0:.0f}s")
            if cover >= COVER_TARGET:
                break
            # --- 다음 목적지: 목적지 주변이 아직 미지이고 남은 경로가 있으면 그대로, 아니면 다시 고른다 ---
            cur = int(true[1]) * self.C + int(true[0])
            if plan is None or len(plan) < 2 or not self._still_frontier(plan[-1]):
                target, path = self.pick_target(cur)
                if target is None or len(path) < 2:
                    break
                plan = path
                self.replans += 1
            pts = np.array([[p % self.C + 0.5, p // self.C + 0.5] for p in plan])
            seg = np.r_[0, np.cumsum(np.hypot(*np.diff(pts, axis=0).T))] * self.cell
            nxt = seg[-1] if seg[-1] <= STOP_EVERY_M * 1.3 else STOP_EVERY_M
            k = int(np.searchsorted(seg, nxt))
            k = min(max(k, 1), len(pts) - 1)
            leg = pts[1:k + 1]
            # 참 이동: 경로 위 점들을 지난다. VO/SLAM: 구간마다 거리·방향 오차 누적
            prev = true.copy()
            for p in leg:
                d = p - prev
                L = np.hypot(*d)
                head_bias += self.rng.normal(0, np.radians(VO_HEAD_SIGMA_DEG)) * np.sqrt(L * self.cell / 100)
                s = 1 + self.rng.normal(0, VO_SCALE_SIGMA)
                rot = lambda a: np.array([np.cos(a) * d[0] - np.sin(a) * d[1], np.sin(a) * d[0] + np.cos(a) * d[1]]) * s
                vo = vo + rot(head_bias); slam = slam + rot(head_bias - slam_head_off)
                prev = p
            self.dist_m.append(self.dist_m[-1] + seg[k])
            true = leg[-1].copy()
            plan = plan[k:]
        self.true_pos = np.array(self.true_pos); self.vo_pos = np.array(self.vo_pos); self.slam_pos = np.array(self.slam_pos)
        self.dist_m = np.array(self.dist_m[:len(self.true_pos)])
        self.slam_corrected = self._pose_graph()
        return self

    def _pose_graph(self):
        """루프 클로저 사이 구간의 위치를 선형으로 나눠 고친다 (간단한 포즈 그래프 근사)."""
        P = self.slam_pos.copy()
        for i, prev_i, corr in self.closures:
            n = i - prev_i
            if n <= 0:
                continue
            w = (np.arange(prev_i + 1, i) - prev_i) / n
            P[prev_i + 1:i] += w[:, None] * corr[None, :]
        return P

    def build_map(self, poses, upto=None):
        """정지별 관측을 주어진 위치 추정으로 옮겨 쌓은 고도·위험도 지도."""
        R, C = self.R, self.C
        hs = np.zeros(R * C); hw = np.zeros(R * C); rs = np.zeros(R * C); rn = np.zeros(R * C)
        n = len(self.obs) if upto is None else upto
        for i in range(n):
            lin, mh, mr, w = self.obs[i]
            off = poses[i] - self.true_pos[i]
            ox, oy = int(np.rint(off[0])), int(np.rint(off[1]))
            x = lin % C + ox; y = lin // C + oy
            ok = (x >= 0) & (y >= 0) & (x < C) & (y < R)
            l2 = y[ok] * C + x[ok]
            np.add.at(hs, l2, mh[ok] * w[ok]); np.add.at(hw, l2, w[ok])
            np.add.at(rs, l2, mr[ok]); np.add.at(rn, l2, 1)
        hmap = np.where(hw > 0, hs / np.maximum(hw, 1e-12), np.nan).reshape(R, C)
        rmap = np.where(rn > 0, rs / np.maximum(rn, 1), np.nan).reshape(R, C)
        return hmap, rmap

    def metrics(self, hmap, rmap):
        S = self.S
        m = np.isfinite(rmap) & S["valid"]
        est, tru = (rmap > HIGH_RISK) & m, (np.nan_to_num(S["risk"]) > HIGH_RISK) & m
        un = (est | tru).sum()
        return {"iou_high_risk": float((est & tru).sum() / un) if un else float("nan"),
                "height_rmse_m": float(np.sqrt(np.nanmean((hmap[m] - S["hf"][m]) ** 2))),
                "mapped_pct": float(m.sum() / S["valid"].sum() * 100)}


def render(E, site_id, out_dir, max_frames=420, fps=20):
    S = E.S
    n = len(E.true_pos)
    step = max(1, int(np.ceil(n / max_frames)))
    frames = list(range(0, n, step)) + ([n - 1] if (n - 1) % step else [])
    cell = E.cell
    hours = E.dist_m / DRIVE_M_PER_H + np.arange(n) * SCAN_MIN / 60
    video_s = len(frames) / fps
    speedup = hours[-1] * 3600 / video_s
    err_vo = np.linalg.norm(E.vo_pos - E.true_pos, axis=1) * cell
    err_sl = np.linalg.norm(E.slam_pos - E.true_pos, axis=1) * cell
    ext = [0, E.C * cell / 1000, E.R * cell / 1000, 0]
    k = cell / 1000
    fig = plt.figure(figsize=(14, 7.6), facecolor="#0b0e15")
    gs = fig.add_gridspec(2, 2, width_ratios=[1.15, 1], height_ratios=[1, 0.42], hspace=0.28, wspace=0.12)
    ax0, ax1, ax2 = fig.add_subplot(gs[:, 0]), fig.add_subplot(gs[0, 1]), fig.add_subplot(gs[1, 1])
    for a in (ax0, ax1, ax2):
        a.set_facecolor("#0b0e15"); a.tick_params(colors="#9aa3b5", labelsize=8)
        for sp in a.spines.values(): sp.set_color("#283041")
    known_acc = np.zeros(E.R * E.C, bool)
    hs = np.zeros(E.R * E.C); rs = np.zeros(E.R * E.C); rn = np.zeros(E.R * E.C)
    base_rgb = S["basemap"].astype(float) / 255
    bx, by = S["base"]
    state = {"done": 0}

    def accumulate(upto):
        for i in range(state["done"], upto + 1):
            lin, mh, mr, w = E.obs[i]
            off = E.slam_pos[i] - E.true_pos[i]
            ox, oy = int(np.rint(off[0])), int(np.rint(off[1]))
            x = lin % E.C + ox; y = lin // E.C + oy
            ok = (x >= 0) & (y >= 0) & (x < E.C) & (y < E.R)
            l2 = y[ok] * E.C + x[ok]
            np.add.at(rs, l2, mr[ok]); np.add.at(rn, l2, 1)
            known_acc[E.obs[i][0]] = True
        state["done"] = upto + 1

    im0 = ax0.imshow(base_rgb, extent=ext)
    im1 = ax1.imshow(np.full((E.R, E.C), np.nan), cmap=RISK_CMAP, vmin=0, vmax=1, extent=ext)
    ax1.set_facecolor("#05070a")
    l_true, = ax0.plot([], [], color="#ffffff", lw=1.0, label="true path")
    l_vo, = ax0.plot([], [], color="#ef6b5e", lw=0.9, ls="--", label="VO only")
    l_sl, = ax0.plot([], [], color="#3fc1cc", lw=0.9, label="SLAM (VO + loop closure)")
    scan_pt, = ax0.plot([], [], "o", color="#ffd23f", ms=6, mec="k")
    ax0.plot((bx + 0.5) * k, (by + 0.5) * k, marker="*", color="#a7e8a0", ms=14, mec="k", ls="")
    ax0.legend(loc="lower left", fontsize=8, facecolor="#151a23", edgecolor="#283041", labelcolor="#e7eaf0")
    e_vo, = ax2.plot([], [], color="#ef6b5e", lw=1.2, label="VO only")
    e_sl, = ax2.plot([], [], color="#3fc1cc", lw=1.2, label="SLAM")
    ax2.set_xlim(0, E.dist_m[-1] / 1000 * 1.02); ax2.set_ylim(0, max(10, err_vo.max() * 1.1))
    ax2.set_xlabel("distance driven (km)", color="#9aa3b5", fontsize=8); ax2.set_ylabel("position error (m)", color="#9aa3b5", fontsize=8)
    ax2.legend(fontsize=8, facecolor="#151a23", edgecolor="#283041", labelcolor="#e7eaf0")
    ax1.set_title("risk map built by SLAM (blue low -> red high), black = not yet seen", color="#e7eaf0", fontsize=9)
    title = fig.suptitle("", color="#e7eaf0", fontsize=11)

    def update(fi):
        i = frames[fi]
        accumulate(i)
        dim = np.where(known_acc.reshape(E.R, E.C)[..., None], base_rgb, base_rgb * 0.25)
        cur = E.obs[i][0]
        hl = dim.reshape(-1, 3); hl[cur] = hl[cur] * 0.6 + np.array([1.0, 0.82, 0.25]) * 0.4
        im0.set_data(dim)
        rmap = np.where(rn > 0, rs / np.maximum(rn, 1), np.nan).reshape(E.R, E.C)
        im1.set_data(rmap)
        tp, vp, sp = E.true_pos[:i + 1] * k, E.vo_pos[:i + 1] * k, E.slam_pos[:i + 1] * k
        l_true.set_data(tp[:, 0], tp[:, 1]); l_vo.set_data(vp[:, 0], vp[:, 1]); l_sl.set_data(sp[:, 0], sp[:, 1])
        scan_pt.set_data([tp[-1, 0]], [tp[-1, 1]])
        e_vo.set_data(E.dist_m[:i + 1] / 1000, err_vo[:i + 1]); e_sl.set_data(E.dist_m[:i + 1] / 1000, err_sl[:i + 1])
        cov = known_acc.reshape(E.R, E.C)[S["valid"]].mean() * 100
        ncl = sum(1 for c in E.closures if c[0] <= i)
        title.set_text(f"{S['name']}  |  stop {i}/{n - 1}  |  {E.dist_m[i] / 1000:.1f} km driven  |  mission {hours[i] / 24.66:.1f} sol "
                       f"({hours[i]:.0f} h)  |  mapped {cov:.0f}%  |  loop closures {ncl}  |  playback x{speedup:,.0f}")
        return im0, im1, l_true, l_vo, l_sl, scan_pt, e_vo, e_sl, title

    ani = animation.FuncAnimation(fig, update, frames=len(frames), blit=False)
    out = f"{out_dir}/slam_{site_id}.mp4"
    ani.save(out, writer=animation.FFMpegWriter(fps=fps, bitrate=3000), dpi=100, savefig_kwargs={"facecolor": "#0b0e15"})
    plt.close(fig)
    return out, speedup, video_s


def final_figure(E, maps, site_id, out_dir, stats):
    S = E.S
    cell = E.cell; k = cell / 1000
    ext = [0, E.C * cell / 1000, E.R * cell / 1000, 0]
    fig, axes = plt.subplots(1, 4, figsize=(20, 6.4), facecolor="#0b0e15")
    panels = [("true risk (HiRISE DTM)", S["risk"]), ("map from true poses (oracle)", maps["oracle"][1]),
              ("map from VO only", maps["vo"][1]), ("map from SLAM (loop closure + pose graph)", maps["slam"][1])]
    for ax, (t, r) in zip(axes, panels):
        ax.set_facecolor("#05070a"); ax.imshow(r, cmap=RISK_CMAP, vmin=0, vmax=1, extent=ext)
        ax.set_title(t, color="#e7eaf0", fontsize=9); ax.tick_params(colors="#9aa3b5", labelsize=7)
    axes[0].plot(E.true_pos[:, 0] * k, E.true_pos[:, 1] * k, color="w", lw=0.5)
    axes[2].plot(E.vo_pos[:, 0] * k, E.vo_pos[:, 1] * k, color="#ef6b5e", lw=0.5)
    axes[3].plot(E.slam_corrected[:, 0] * k, E.slam_corrected[:, 1] * k, color="#3fc1cc", lw=0.5)
    m = stats["maps"]
    fig.suptitle(f"{S['name']}: {stats['n_stops']} stops, {stats['distance_km']:.1f} km, {stats['mission_sols']:.1f} sol, "
                 f"mapped {stats['coverage_pct']:.0f}% | high-risk IoU oracle {m['oracle']['iou_high_risk']:.2f} / "
                 f"VO {m['vo']['iou_high_risk']:.2f} / SLAM {m['slam']['iou_high_risk']:.2f} | "
                 f"final pose error VO {stats['final_err_vo_m']:.0f} m, SLAM {stats['final_err_slam_m']:.0f} m",
                 color="#e7eaf0", fontsize=10)
    fig.tight_layout(); out = f"{out_dir}/slam_{site_id}_final.png"
    fig.savefig(out, dpi=90, facecolor="#0b0e15"); plt.close(fig)
    return out


def main(site_id, video=True):
    out_dir = f"../outputs/slam_sites/{site_id}"
    os.makedirs(out_dir, exist_ok=True)
    S = load_site(site_id)
    print(f"[{site_id}] 격자 {S['h'].shape}, 칸 {S['cell']:.2f} m, 유효 {S['valid'].sum() * (S['cell'] / 1000) ** 2:.1f} km²")
    t0 = time.time()
    E = Explorer(S).run()
    sim_s = time.time() - t0
    maps = {"oracle": E.build_map(E.true_pos), "vo": E.build_map(E.vo_pos), "slam": E.build_map(E.slam_corrected)}
    n = len(E.true_pos)
    hours = E.dist_m[-1] / DRIVE_M_PER_H + n * SCAN_MIN / 60
    err_vo = np.linalg.norm(E.vo_pos - E.true_pos, axis=1) * E.cell
    err_sl = np.linalg.norm(E.slam_corrected - E.true_pos, axis=1) * E.cell
    stats = {"site": site_id, "n_stops": int(n), "distance_km": float(E.dist_m[-1] / 1000), "mission_hours": float(hours),
             "mission_sols": float(hours / 24.66), "coverage_pct": float((E.known & S["valid"]).sum() / S["valid"].sum() * 100),
             "loop_closures": len(E.closures), "replans": int(E.replans), "final_err_vo_m": float(err_vo[-1]), "max_err_vo_m": float(err_vo.max()),
             "final_err_slam_m": float(err_sl[-1]), "max_err_slam_m": float(err_sl.max()),
             "maps": {k_: E.metrics(*v) for k_, v in maps.items()}, "sim_seconds": sim_s,
             "params": {"mast_m": MAST_M, "range_m": RANGE_M, "stop_every_m": STOP_EVERY_M, "vo_scale_sigma": VO_SCALE_SIGMA,
                        "vo_heading_sigma_deg_per_100m": VO_HEAD_SIGMA_DEG, "loop_min_overlap": LOOP_MIN_OVERLAP,
                        "loop_residual_m": LOOP_RESIDUAL_M, "loop_residual_deg": LOOP_RESIDUAL_DEG, "drive_m_per_h": DRIVE_M_PER_H, "scan_min": SCAN_MIN, "seed": SEED}}
    final_figure(E, maps, site_id, out_dir, stats)
    if video:
        t1 = time.time()
        out, speedup, vs = render(E, site_id, out_dir)
        stats.update(video=os.path.basename(out), playback_speedup=speedup, video_seconds=vs, render_seconds=time.time() - t1)
    json.dump(stats, open(f"{out_dir}/slam_{site_id}_stats.json", "w"), indent=1)
    print(json.dumps({k_: (round(v, 2) if isinstance(v, float) else v) for k_, v in stats.items() if k_ not in ("params",)}, ensure_ascii=False))
    return stats


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    for sid in (args or ["jezero", "aram"]):
        main(sid, video="--no-video" not in sys.argv)

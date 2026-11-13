import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

SCRATCH = "../data/devon_island"

idx, east, north, elev = [], [], [], []
with open(f"{SCRATCH}/gps-topocentric.txt") as f:
    for line in f:
        parts = line.split()
        idx.append(int(parts[0]))
        east.append(float(parts[1]))
        north.append(float(parts[2]))
        elev.append(float(parts[3]))

idx = np.array(idx)
east = np.array(east)
north = np.array(north)
elev = np.array(elev)

total_dist = np.sum(np.hypot(np.diff(east), np.diff(north)))
print(f"frames: {len(idx)}")
print(f"total path length: {total_dist:.1f} m")
print(f"elevation range: {elev.min():.1f} to {elev.max():.1f} m")
print(f"bounding box east: {east.min():.1f} to {east.max():.1f} m")
print(f"bounding box north: {north.min():.1f} to {north.max():.1f} m")

fig, axes = plt.subplots(1, 2, figsize=(13, 5.5), facecolor="#0b0e15")
for ax in axes:
    ax.set_facecolor("#0b0e15")
    for spine in ax.spines.values():
        spine.set_color("#262d3d")
    ax.tick_params(colors="#a7aec1", labelsize=8)

sc = axes[0].scatter(east, north, c=elev, cmap="terrain", s=1.2, linewidths=0)
axes[0].plot(east[0], north[0], "o", color="#5cbcc3", markersize=8, label="start")
axes[0].plot(east[-1], north[-1], "o", color="#e08a76", markersize=8, label="end")
axes[0].set_title(f"Real DGPS trajectory — {len(idx)} frames, {total_dist/1000:.2f} km", color="#e9ebf2", fontsize=10.5)
axes[0].set_xlabel("easting (m)", color="#a7aec1", fontsize=9)
axes[0].set_ylabel("northing (m)", color="#a7aec1", fontsize=9)
axes[0].set_aspect("equal")
axes[0].legend(facecolor="#141926", edgecolor="#262d3d", labelcolor="#e9ebf2", fontsize=8)
cbar = fig.colorbar(sc, ax=axes[0], fraction=0.046, pad=0.03)
cbar.set_label("elevation (m)", color="#e9ebf2", fontsize=8.5)
cbar.ax.yaxis.set_tick_params(color="#e9ebf2")
plt.setp(cbar.ax.get_yticklabels(), color="#e9ebf2")

axes[1].plot(idx, elev, color="#e0ac53", linewidth=1)
axes[1].set_title("Elevation profile along traverse", color="#e9ebf2", fontsize=10.5)
axes[1].set_xlabel("image index (frame #)", color="#a7aec1", fontsize=9)
axes[1].set_ylabel("elevation (m)", color="#a7aec1", fontsize=9)
axes[1].grid(color="#1c2230", linewidth=0.6)

fig.tight_layout()
fig.savefig("../outputs/trajectory_full.png", dpi=140, bbox_inches="tight", facecolor=fig.get_facecolor())
print("saved trajectory_full.png")

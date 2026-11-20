"""Run the weekday simulation and write layers, tables, figures and viewer data.

    python -m twin.build                 # full population, default seed
    python -m twin.build --scale 0.2     # quick run with 20% of residents
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from . import schedules as S  # noqa: E402
from .layers import ROADS, coordinates, places_table, write_layers  # noqa: E402
from .model import CampusTwin  # noqa: E402
from .store import run_queries, write_db  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"
ACTIVITY_COLORS = {
    "home": "#d9d8d3", "class": "#2a78d6", "study": "#1baf7a", "meal": "#eb6834", "library": "#6250d6",
    "sports": "#008300", "market": "#eda100", "health": "#e87ba4", "travel": "#52514e",
}
KIND_COLORS = {"hall": "#eb6834", "academic": "#2a78d6", "amenity": "#eda100", "sports_open": "#008300",
               "gate": "#52514e"}


def _style(ax):
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=9)
    ax.yaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def _hour_ticks(ax):
    ticks = [S.step_of(h) for h in range(6, 25, 3)]
    ax.set_xticks(ticks)
    ax.set_xticklabels([f"{h:02d}:00" for h in range(6, 25, 3)])


def fig_time_use(time_use: pd.DataFrame, path: Path):
    avg = time_use.groupby(["step", "activity"])["agents"].mean().unstack()[list(S.ACTIVITIES)]
    share = avg.div(avg.sum(axis=1), axis=0) * 100
    fig, ax = plt.subplots(figsize=(10, 4.6))
    ax.stackplot(share.index, share.T.values, colors=[ACTIVITY_COLORS[a] for a in share.columns],
                 labels=share.columns, linewidth=0.6, edgecolor="white")
    _style(ax)
    _hour_ticks(ax)
    ax.set_xlim(0, S.N_STEPS - 1)
    ax.set_ylim(0, 100)
    ax.set_ylabel("Share of residents (%)", color=MUTED)
    ax.set_title("What residents are doing on an average weekday", loc="left", color=INK, fontsize=12)
    ax.legend(ncol=9, fontsize=8, frameon=False, loc="upper left", bbox_to_anchor=(0, -0.1))
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def fig_occupancy(occ: pd.DataFrame, places: pd.DataFrame, path: Path):
    occ = occ[~occ["kind"].isin(["hall", "gate"])]
    avg = occ.groupby(["place", "step"])["people"].mean().unstack()
    cap = places.set_index("place")["capacity"]
    util = avg.div(cap[avg.index], axis=0) * 100
    util = util.loc[util.max(axis=1).sort_values(ascending=False).index]
    fig, ax = plt.subplots(figsize=(10, 4.4))
    im = ax.imshow(util.values, aspect="auto", cmap="Blues", vmin=0, vmax=100, interpolation="nearest")
    ax.set_yticks(range(len(util)))
    ax.set_yticklabels(util.index, fontsize=9, color=INK)
    _hour_ticks(ax)
    ax.tick_params(colors=MUTED, labelsize=9, length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    cb = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.01)
    cb.set_label("Share of capacity in use (%)", color=MUTED, fontsize=9)
    cb.outline.set_visible(False)
    ax.set_title("Building use on an average weekday", loc="left", color=INK, fontsize=12)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def fig_road_map(road: pd.DataFrame, places: pd.DataFrame, path: Path):
    xy = coordinates()
    daily = road.groupby("segment")["trips"].sum() / road["day"].nunique()
    top = daily.max()
    fig, ax = plt.subplots(figsize=(8.2, 8.2))
    for a, b in ROADS:
        seg = f"{a}--{b}"
        v = daily.get(seg, 0.0)
        (x1, y1), (x2, y2) = xy[a], xy[b]
        ax.plot([x1, x2], [y1, y2], color="#c3c2b7", linewidth=1.0, solid_capstyle="round", zorder=1)
        if v > 0:
            ax.plot([x1, x2], [y1, y2], color="#2a78d6", alpha=0.85, linewidth=1 + 11 * v / top,
                    solid_capstyle="round", zorder=2)
    for kind, grp in places.groupby("kind"):
        ax.scatter(grp["x"], grp["y"], s=70, color=KIND_COLORS[kind], edgecolor="white", linewidth=2,
                   zorder=3, label=kind.replace("_", " ").replace("sports open", "sports and open space"))
        for _, r in grp.iterrows():
            ax.annotate(r["place"], (r["x"], r["y"]), xytext=(6, 5), textcoords="offset points",
                        fontsize=7.5, color=INK, zorder=4)
    ax.set_aspect("equal")
    ax.set_axis_off()
    ax.set_title("Average weekday trips by road segment (line width)", loc="left", color=INK, fontsize=12)
    ax.legend(frameon=False, fontsize=8, loc="lower right")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def fig_weekday_trips(trips: pd.DataFrame, path: Path):
    counts = trips.groupby(["day", "purpose"]).size().unstack(fill_value=0).reindex(list(S.DAYS))
    order = [p for p in ("class", "home", "meal", "library", "study", "sports", "market", "health") if p in counts]
    counts = counts[order]
    fig, ax = plt.subplots(figsize=(10, 4.2))
    bottom = np.zeros(len(counts))
    for p in order:
        ax.bar(counts.index, counts[p], bottom=bottom, color=ACTIVITY_COLORS[p], width=0.55,
               edgecolor="white", linewidth=2, label=p)
        bottom += counts[p].to_numpy()
    for i, total in enumerate(bottom):
        ax.text(i, total + 300, f"{int(total):,}", ha="center", fontsize=9, color=INK)
    _style(ax)
    ax.set_ylabel("Trips", color=MUTED)
    ax.set_title("Trips per weekday by purpose of the destination", loc="left", color=INK, fontsize=12)
    ax.legend(ncol=len(order), fontsize=8, frameon=False, loc="upper left", bbox_to_anchor=(0, -0.08))
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def write_viewer_data(twin: CampusTwin, occ: pd.DataFrame, road: pd.DataFrame, path: Path):
    places = places_table()
    names = [p["place"] for p in places]
    xy = coordinates()
    segments = [{"id": f"{a}--{b}", "a": list(xy[a]), "b": list(xy[b])} for a, b in ROADS]
    seg_index = {s["id"]: i for i, s in enumerate(segments)}
    occupancy, roads = {}, {}
    for day in S.DAYS:
        grid = occ[occ["day"] == day].pivot(index="step", columns="place", values="people")[names]
        occupancy[day] = grid.to_numpy().astype(int).tolist()
        hours = np.zeros((24, len(segments)), dtype=int)
        for h, seg, n in road[road["day"] == day][["hour", "segment", "trips"]].itertuples(index=False):
            hours[h, seg_index[seg]] += n
        roads[day] = hours.tolist()
    data = {"days": list(S.DAYS), "times": [S.clock(s) for s in range(S.N_STEPS)], "places": places,
            "segments": segments, "occupancy": occupancy, "roads": roads, "residents": len(twin.agents)}
    path.write_text("window.TWIN_DATA = " + json.dumps(data, separators=(",", ":")) + ";\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scale", type=float, default=1.0, help="share of hall capacity simulated")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default=str(ROOT / "outputs"))
    args = ap.parse_args(argv)

    out = Path(args.out)
    figs = ROOT / "docs" / "figures"
    for p in (out, out / "sql", figs):
        p.mkdir(parents=True, exist_ok=True)
    write_layers(ROOT / "layers")

    twin = CampusTwin(scale=args.scale, seed=args.seed).run_week()
    trips, occ, tu, road = twin.trips(), twin.occupancy(), twin.time_use(), twin.road_usage()
    places = pd.DataFrame(places_table())

    trips.to_csv(out / "trips.csv.gz", index=False)
    occ.to_csv(out / "occupancy.csv.gz", index=False)
    road.to_csv(out / "road_usage.csv", index=False)
    con = write_db({"trips": trips, "occupancy": occ, "time_use": tu, "road_usage": road, "places": places},
                   out / "campus.db")
    for name, df in run_queries(con).items():
        df.to_csv(out / "sql" / f"{name}.csv", index=False)

    fig_time_use(tu, figs / "time_use.png")
    fig_occupancy(occ, places, figs / "building_use.png")
    fig_road_map(road, places, figs / "road_usage_map.png")
    fig_weekday_trips(trips, figs / "weekday_trips.png")
    write_viewer_data(twin, occ, road, ROOT / "web" / "data.js")

    print(f"{len(twin.agents):,} residents, {len(trips):,} trips over {len(S.DAYS)} weekdays")
    print(f"tables in {out}, figures in {figs}, viewer data in web/data.js")


if __name__ == "__main__":
    main()

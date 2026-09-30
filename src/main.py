"""Run the full benchmark: OR-Tools CVRPTW vs. nearest-neighbor baseline.

Usage:
    python src/main.py [--time-limit 45]

Writes:
    data/deliveries.csv            (generated if missing)
    outputs/routes.csv             optimized route plan with arrival times
    outputs/comparison_summary.json / .csv
    outputs/route_map.png          optimized routes plotted over the metro area
"""

import argparse
import csv
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import generate_data
from baseline import nearest_neighbor
from routing_utils import haversine_matrix, to_miles
from solver import solve_cvrptw

ROOT = Path(__file__).resolve().parent.parent


def route_miles(routes, df: pd.DataFrame) -> float:
    dist = haversine_matrix(df["lat"].to_numpy(), df["lon"].to_numpy())
    node_of = {int(sid): i for i, sid in enumerate(df["stop_id"])}
    total_m = 0.0
    for route in routes:
        seq = [0] + [node_of[s] for s in route] + [0]  # depot out and back
        total_m += sum(dist[a, b] for a, b in zip(seq, seq[1:]))
    return to_miles(total_m)


def summarize(name, routes, n_stops, extra=None):
    m = {
        "method": name,
        "vehicles_used": len(routes),
        "stops_served": sum(len(r) for r in routes),
        "stops_dropped": n_stops - sum(len(r) for r in routes),
        "total_route_miles": 0.0,  # filled in by caller
        "avg_stops_per_route": round(
            sum(len(r) for r in routes) / max(len(routes), 1), 1
        ),
    }
    if extra:
        m.update(extra)
    return m


def write_routes_csv(result, df, path):
    by_id = df.set_index("stop_id")
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["route", "position", "stop_id", "lat", "lon",
                    "arrival_time", "demand_packages"])
        for r_i, (route, arrivals) in enumerate(
                zip(result.routes, result.arrivals), start=1):
            for pos, (sid, arr) in enumerate(zip(route, arrivals), start=1):
                row = by_id.loc[sid]
                hh, mm = divmod(int(round(arr)), 60)
                w.writerow([r_i, pos, sid, f"{row['lat']:.6f}",
                            f"{row['lon']:.6f}", f"{hh:02d}:{mm:02d}",
                            int(row["demand_packages"])])


def plot_map(result, df, path):
    by_id = df.set_index("stop_id")
    fig, ax = plt.subplots(figsize=(11, 9))
    for r_i, route in enumerate(result.routes):
        lats = [by_id.loc[s, "lat"] for s in route]
        lons = [by_id.loc[s, "lon"] for s in route]
        cols = ["#e6194B", "#3cb44b", "#4363d8", "#f58231", "#911eb4",
                "#42d4f4", "#f032e6", "#bfef45", "#fabed4", "#469990",
                "#dcbeff", "#9A6324", "#800000", "#aaffc3", "#808000",
                "#ffd8b1", "#000075", "#a9a9a9", "#ffe119", "#1f77b4",
                "#2ca02c", "#d62728", "#9467bd"]
        c = cols[r_i % len(cols)]
        ax.plot([df.loc[0, "lon"], *lons, df.loc[0, "lon"]],
                [df.loc[0, "lat"], *lats, df.loc[0, "lat"]],
                "-", color=c, lw=1.0, alpha=0.75, zorder=1)
        ax.scatter(lons, lats, s=26, color=c, edgecolors="white",
                   linewidths=0.4, zorder=2)
    depot = df[df["is_depot"] == 1].iloc[0]
    ax.scatter([depot["lon"]], [depot["lat"]], marker="*", s=340,
               color="black", zorder=3, label="Depot (Chicago)")
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_title("Final-Mile Delivery Routes — OR-Tools CVRPTW "
                 f"({len(result.routes)} vehicles, 300 stops)")
    if len(result.routes) <= 20:
        ax.legend(loc="upper left", fontsize=7, ncol=2, framealpha=0.9)
    else:
        ax.legend(loc="upper left", fontsize=8)
    ax.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--time-limit", type=int, default=45,
                    help="OR-Tools solve time limit in seconds")
    args = ap.parse_args()

    data_path = ROOT / "data" / "deliveries.csv"
    if not data_path.exists():
        generate_data.main()
    df = pd.read_csv(data_path)
    n_stops = int((df["is_depot"] == 0).sum())
    print(f"Loaded {n_stops} stops + depot; total demand = "
          f"{int(df['demand_packages'].sum())} packages")

    print(f"Solving CVRPTW with OR-Tools (limit {args.time_limit}s)...")
    opt = solve_cvrptw(df, time_limit_s=args.time_limit)
    base = nearest_neighbor(df)

    opt_m = summarize("OR-Tools CVRPTW", opt.routes, n_stops,
                      {"solve_seconds": round(opt.solve_seconds, 1)})
    base_m = summarize("Nearest-neighbor greedy", base.routes, n_stops)
    opt_m["total_route_miles"] = round(route_miles(opt.routes, df), 1)
    base_m["total_route_miles"] = round(route_miles(base.routes, df), 1)

    miles_cut = 100 * (1 - opt_m["total_route_miles"] / base_m["total_route_miles"])
    veh_cut = base_m["vehicles_used"] - opt_m["vehicles_used"]
    summary = {
        "dataset": "synthetic: 1 depot + 300 stops, Chicago area, seed 42",
        "baseline": base_m,
        "optimized": opt_m,
        "improvement": {
            "miles_reduction_pct": round(miles_cut, 1),
            "vehicles_saved": veh_cut,
            "dropped_stops_optimized": opt.dropped,
        },
    }

    out = ROOT / "outputs"
    out.mkdir(exist_ok=True)
    (out / "comparison_summary.json").write_text(json.dumps(summary, indent=2))
    pd.DataFrame([base_m, opt_m]).to_csv(out / "comparison_summary.csv", index=False)
    write_routes_csv(opt, df, out / "routes.csv")
    plot_map(opt, df, out / "route_map.png")

    print(json.dumps(summary, indent=2))
    print(f"\nOutputs written to {out}")


if __name__ == "__main__":
    main()

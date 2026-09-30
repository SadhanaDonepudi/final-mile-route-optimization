"""Nearest-neighbor greedy baseline.

From each route start, repeatedly drive to the nearest unvisited stop that
still fits the remaining vehicle capacity and can be reached before its
delivery window closes. When no stop fits, close the route and start a new
vehicle. This is the kind of manual/greedy dispatch the optimized solution
is benchmarked against.
"""

from dataclasses import dataclass, field

import pandas as pd

from routing_utils import haversine_matrix, travel_seconds
from solver import VEHICLE_CAPACITY


@dataclass
class BaselineResult:
    routes: list = field(default_factory=list)  # stop_ids in visit order, depot excluded


def nearest_neighbor(df: pd.DataFrame) -> BaselineResult:
    df = df.sort_values("stop_id").reset_index(drop=True)
    depot_i = 0  # node index of the depot
    dist = haversine_matrix(df["lat"].to_numpy(), df["lon"].to_numpy())
    by_id = df.set_index("stop_id")
    node_of = {int(sid): i for i, sid in enumerate(df["stop_id"])}

    unvisited = set(int(s) for s in df.loc[df["is_depot"] == 0, "stop_id"])
    routes = []

    while unvisited:
        route = []
        cur = depot_i
        clock = 8 * 60 * 60  # seconds since midnight; depart at 08:00
        load = 0
        while True:
            best, best_d = None, None
            for sid in unvisited:
                row = by_id.loc[sid]
                if load + row["demand_packages"] > VEHICLE_CAPACITY:
                    continue
                arr = clock + travel_seconds(dist[cur, node_of[sid]])
                if arr > row["window_end_min"] * 60:
                    continue
                d = dist[cur, node_of[sid]]
                if best_d is None or d < best_d:
                    best, best_d = sid, d
            if best is None:
                break
            row = by_id.loc[best]
            arr = clock + travel_seconds(dist[cur, node_of[best]])
            clock = max(arr, row["window_start_min"] * 60) + row["service_time_min"] * 60
            load += int(row["demand_packages"])
            route.append(best)
            unvisited.remove(best)
            cur = node_of[best]
        if route:
            routes.append(route)
        else:
            # A stop that cannot be served even by a fresh vehicle (should not
            # happen with these windows); drop it to guarantee termination.
            unvisited.pop()

    return BaselineResult(routes=routes)

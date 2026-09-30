"""Capacitated VRP with time windows (CVRPTW) solved with Google OR-Tools.

Model:
  - Cost: haversine distance (meters).
  - Capacity dimension: packages per vehicle vs. vehicle capacity.
  - Time dimension: travel time (distance / speed) + service time at each
    stop, per-stop delivery windows, depot window for the full working day,
    waiting allowed (vehicles may arrive early and wait).
  - Disjunction with a large penalty so the solver may drop a stop rather
    than return infeasible; dropped stops are reported, not hidden.

Search: PATH_CHEAPEST_ARC first solution + GUIDED_LOCAL_SEARCH, time-limited.
"""

import time
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from ortools.constraint_solver import pywrapcp, routing_enums_pb2

from routing_utils import SPEED_MPS, haversine_matrix

VEHICLE_CAPACITY = 60        # packages per van
NUM_VEHICLES = 40            # available fleet (upper bound)
FIXED_VEHICLE_COST_M = 10_000  # encourages using fewer vehicles
DROP_PENALTY_M = 1_000_000     # per dropped stop (meters-equivalent)
DAY0_SEC = 8 * 3600            # 08:00 in seconds since midnight


@dataclass
class SolveResult:
    routes: list = field(default_factory=list)   # list of routes; each a list of stop_ids in visit order
    arrivals: list = field(default_factory=list)  # parallel list of arrival times (min since midnight)
    dropped: list = field(default_factory=list)   # stop_ids not served
    solve_seconds: float = 0.0


def solve_cvrptw(df: pd.DataFrame, time_limit_s: int = 45) -> SolveResult:
    df = df.sort_values("stop_id").reset_index(drop=True)
    n = len(df)  # node 0 is the depot (stop_id 0 sorts first)

    lats = df["lat"].to_numpy()
    lons = df["lon"].to_numpy()
    dist = haversine_matrix(lats, lons)
    demands = df["demand_packages"].to_numpy()
    service_s = df["service_time_min"].to_numpy() * 60
    # Time windows in seconds since depot opening (08:00).
    win_start = (df["window_start_min"].to_numpy() - 8 * 60) * 60
    win_end = (df["window_end_min"].to_numpy() - 8 * 60) * 60
    horizon = 9 * 3600  # 08:00-17:00

    manager = pywrapcp.RoutingIndexManager(n, NUM_VEHICLES, 0)
    routing = pywrapcp.RoutingModel(manager)

    dist_idx = routing.RegisterTransitCallback(
        lambda i, j: int(dist[manager.IndexToNode(i), manager.IndexToNode(j)])
    )
    routing.SetArcCostEvaluatorOfAllVehicles(dist_idx)
    routing.SetFixedCostOfAllVehicles(FIXED_VEHICLE_COST_M)

    demand_idx = routing.RegisterUnaryTransitCallback(
        lambda i: int(demands[manager.IndexToNode(i)])
    )
    routing.AddDimensionWithVehicleCapacity(
        demand_idx, 0, [VEHICLE_CAPACITY] * NUM_VEHICLES, True, "Capacity"
    )

    def time_callback(i, j):
        a, b = manager.IndexToNode(i), manager.IndexToNode(j)
        return int(dist[a, b] / SPEED_MPS) + int(service_s[a])

    time_idx = routing.RegisterTransitCallback(time_callback)
    # max waiting = horizon (waiting allowed), max route time = horizon.
    routing.AddDimension(time_idx, horizon, horizon, False, "Time")
    time_dim = routing.GetDimensionOrDie("Time")
    for node in range(n):
        idx = manager.NodeToIndex(node)
        time_dim.CumulVar(idx).SetRange(int(win_start[node]), int(win_end[node]))
    for v in range(NUM_VEHICLES):
        time_dim.CumulVar(routing.Start(v)).SetRange(0, horizon)
        time_dim.CumulVar(routing.End(v)).SetRange(0, horizon)

    # Allow dropping stops at a steep penalty rather than failing outright.
    for node in range(1, n):
        routing.AddDisjunction([manager.NodeToIndex(node)], DROP_PENALTY_M)

    params = pywrapcp.DefaultRoutingSearchParameters()
    params.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )
    params.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    )
    params.time_limit.FromSeconds(time_limit_s)

    t0 = time.time()
    solution = routing.SolveWithParameters(params)
    elapsed = time.time() - t0
    if solution is None:
        raise RuntimeError("OR-Tools found no solution at all.")

    result = SolveResult(solve_seconds=elapsed)
    for v in range(NUM_VEHICLES):
        idx = routing.Start(v)
        route, arrivals = [], []
        while not routing.IsEnd(idx):
            node = manager.IndexToNode(idx)
            if node != 0:
                route.append(int(df.loc[node, "stop_id"]))
                arr_min = solution.Min(time_dim.CumulVar(idx)) / 60.0 + 8 * 60
                arrivals.append(arr_min)
            idx = solution.Value(routing.NextVar(idx))
        if route:
            result.routes.append(route)
            result.arrivals.append(arrivals)

    served = {s for r in result.routes for s in r}
    all_stops = set(int(s) for s in df.loc[df["is_depot"] == 0, "stop_id"])
    result.dropped = sorted(all_stops - served)
    return result

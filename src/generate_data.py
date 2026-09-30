"""Generate synthetic pharmacy delivery data.

One depot plus 300 delivery stops clustered around a metro area (Chicago).
Seeded RNG so the dataset is reproducible. Saved to data/deliveries.csv.

Columns:
    stop_id          0 = depot, 1..300 = delivery stops
    lat, lon         WGS84 coordinates
    demand_packages  packages to deliver (0 for depot)
    service_time_min minutes spent at the stop
    window_start_min earliest delivery time, minutes since midnight
    window_end_min   latest delivery time, minutes since midnight
    is_depot         1 for the depot row, else 0
"""

from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
N_STOPS = 300
DEPOT_LAT, DEPOT_LON = 41.8781, -87.6298  # downtown Chicago, IL
DAY_START_MIN = 8 * 60   # 08:00
DAY_END_MIN = 17 * 60    # 17:00


def generate(n_stops: int = N_STOPS, seed: int = SEED) -> pd.DataFrame:
    rng = np.random.default_rng(seed)

    # Cluster centers spread around the metro area, stops jittered around them.
    n_clusters = 6
    centers_lat = DEPOT_LAT + rng.normal(0, 0.09, n_clusters)
    centers_lon = DEPOT_LON + rng.normal(0, 0.11, n_clusters)
    cluster = rng.integers(0, n_clusters, n_stops)
    lats = centers_lat[cluster] + rng.normal(0, 0.028, n_stops)
    lons = centers_lon[cluster] + rng.normal(0, 0.034, n_stops)

    demand = rng.integers(1, 9, n_stops)          # 1-8 packages per stop
    service = rng.integers(3, 7, n_stops)         # 3-6 min per stop

    # Delivery windows of 1.5-3 h inside the 08:00-17:00 working day.
    w_start = rng.integers(DAY_START_MIN, 14 * 60, n_stops)
    width = rng.integers(90, 181, n_stops)
    w_end = np.minimum(w_start + width, DAY_END_MIN)

    stops = pd.DataFrame({
        "stop_id": np.arange(1, n_stops + 1),
        "lat": lats,
        "lon": lons,
        "demand_packages": demand,
        "service_time_min": service,
        "window_start_min": w_start,
        "window_end_min": w_end,
        "is_depot": 0,
    })

    depot = pd.DataFrame([{
        "stop_id": 0,
        "lat": DEPOT_LAT,
        "lon": DEPOT_LON,
        "demand_packages": 0,
        "service_time_min": 0,
        "window_start_min": DAY_START_MIN,
        "window_end_min": DAY_END_MIN,
        "is_depot": 1,
    }])

    return pd.concat([depot, stops], ignore_index=True)


def main() -> None:
    out = Path(__file__).resolve().parent.parent / "data" / "deliveries.csv"
    df = generate()
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    print(f"Wrote {out} ({len(df)} rows: 1 depot + {len(df) - 1} stops)")


if __name__ == "__main__":
    main()

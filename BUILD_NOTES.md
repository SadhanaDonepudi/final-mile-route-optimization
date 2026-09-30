# Build notes — final-mile-route-optimization

## What was built
A complete, runnable CVRPTW portfolio project:
- `src/generate_data.py` — seeded (42) synthetic dataset: 1 depot (downtown
  Chicago) + 300 stops in 6 metro clusters, 1–8 packages/stop (1,325 total),
  3–6 min service times, 1.5–3 h delivery windows inside 08:00–17:00.
  Saved to `data/deliveries.csv`.
- `src/solver.py` — OR-Tools RoutingModel CVRPTW: capacity dimension
  (60 packages/van), time dimension (haversine distance ÷ ~30 mph + service
  time, per-stop windows, depot day window, waiting allowed), drop penalty
  so infeasibility degrades gracefully, PATH_CHEAPEST_ARC +
  GUIDED_LOCAL_SEARCH, 45 s limit, small fixed vehicle cost.
- `src/baseline.py` — nearest-neighbor greedy respecting capacity and
  window-close times.
- `src/main.py` — end-to-end run: metrics (haversine route miles, vehicles,
  stops/route), `outputs/routes.csv` (route, sequence, arrival times),
  `outputs/comparison_summary.json` + `.csv`, `outputs/route_map.png`.

## Run command
```
cd ~/workspace/github-projects/final-mile-route-optimization
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python src/main.py          # ~60 s wall, incl. 45 s solve
```

## Verified results (actual run, 2026-09-30)
- OR-Tools: **582.6 total miles, 23 vehicles, 300/300 stops served,
  0 dropped**, avg 13.0 stops/route, solve 45.0 s.
- Baseline (nearest neighbor): 789.6 miles, 23 vehicles, 300/300 served,
  avg 13.0 stops/route.
- **Improvement: −26.2% route miles (207 miles), 0 fewer vehicles.**
- Outputs confirmed on disk; routes.csv has exactly 300 stop rows across
  23 routes (8–17 stops each); map PNG inspected visually — routes form
  sensible geographic clusters around the depot.

## Deviations / limitations (honest)
- **Vehicle count did not drop.** 23 vehicles is the bin-packing lower
  bound (1,325 ÷ 60 ≈ 22.1) and both methods achieve it, so no fleet
  reduction is possible on this instance. A second run at 45-package
  capacity showed the same effect (both at the 30-vehicle bound; miles
  −13.5%), so capacity 60 was kept. The resume's methodology mentions
  vehicle reduction from the real project; this synthetic replica's win
  is mileage. Noted in the README rather than tuned away.
- Distances are straight-line haversine, not road-network routing;
  absolute miles are approximate, relative savings are the signal.
- Single average speed (30 mph); no traffic/time-of-day effects.
- OR-Tools is time-limited → near-optimal, not proven optimal.
- Environment note: system Python is PEP-668 externally managed and its
  old matplotlib conflicts with NumPy 2.x pulled by OR-Tools, so the
  project uses its own `.venv` (in `.gitignore`). Nothing was pushed to
  GitHub — left for the parent agent.

"""Health ingest — parses the JSON payload posted by the iOS 'Health Auto Export'
app (HealthKit / Apple Fitness) into a normalized snapshot for the Health panel.

This is a PUSH connector (data arrives via POST), not a scheduled puller.
The payload shape varies slightly by app version, so parsing is tolerant.
"""

# metric name aliases → our normalized keys (HAE uses lowercase snake names)
ALIASES = {
    "steps":          ["step_count", "steps"],
    "active_energy":  ["active_energy", "active_energy_burned"],
    "exercise_min":   ["apple_exercise_time", "exercise_time", "apple_exercise_minutes"],
    "stand_hours":    ["apple_stand_hour", "apple_stand_hours", "stand_time"],
    "resting_hr":     ["resting_heart_rate"],
    "heart_rate":     ["heart_rate"],
    "sleep_hours":    ["sleep_analysis", "sleep_asleep", "sleep"],
    "distance_mi":    ["walking_running_distance", "distance_walking_running"],
}

def _latest_qty(metric):
    """Return the most recent numeric value from a metric's data points."""
    pts = metric.get("data") or []
    if not pts: return None
    # prefer the last point; support 'qty', 'Avg', or asleep totals
    last = pts[-1]
    for k in ("qty", "Avg", "avg", "value", "asleep", "total"):
        if k in last and isinstance(last[k], (int, float)):
            return last[k]
    return None

def _sum_qty(metric):
    pts = metric.get("data") or []
    tot = 0.0; seen = False
    for p in pts:
        v = p.get("qty")
        if isinstance(v, (int, float)): tot += v; seen = True
    return tot if seen else None

def parse(payload: dict) -> dict:
    """Turn a Health Auto Export POST body into a normalized health snapshot."""
    data = payload.get("data", payload)
    metrics = data.get("metrics", []) or []
    by_name = {m.get("name", "").lower(): m for m in metrics if isinstance(m, dict)}

    out = {}
    for key, names in ALIASES.items():
        for n in names:
            if n in by_name:
                m = by_name[n]
                # sums for cumulative metrics, latest for point-in-time
                if key in ("steps", "active_energy", "exercise_min", "stand_hours", "distance_mi", "sleep_hours"):
                    val = _sum_qty(m)
                    if val is None: val = _latest_qty(m)
                else:
                    val = _latest_qty(m)
                if val is not None:
                    out[key] = round(val, 1) if isinstance(val, float) else val
                    out.setdefault("_units", {})[key] = m.get("units")
                break

    workouts = data.get("workouts", []) or []
    out["workouts_today"] = len(workouts)
    if workouts:
        w = workouts[-1]
        out["last_workout"] = w.get("name") or w.get("workoutActivityType")

    # activity-ring style summary the UI can show
    out["rings"] = {
        "move": out.get("active_energy"),
        "exercise": out.get("exercise_min"),
        "stand": out.get("stand_hours"),
    }
    return out

if __name__ == "__main__":
    import json, sys
    sample = {"data": {"metrics": [
        {"name": "step_count", "units": "count", "data": [{"date": "2026-08-05 12:00:00 -0400", "qty": 8432}]},
        {"name": "active_energy", "units": "kcal", "data": [{"qty": 540}]},
        {"name": "apple_exercise_time", "units": "min", "data": [{"qty": 42}]},
        {"name": "resting_heart_rate", "units": "bpm", "data": [{"qty": 58}]},
        {"name": "sleep_analysis", "units": "hr", "data": [{"qty": 7.3}]},
    ], "workouts": [{"name": "Outdoor Run"}]}}
    print(json.dumps(parse(sample), indent=2))

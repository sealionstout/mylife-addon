"""myLife backend — FastAPI. Serves the aggregated /api/dashboard feed and
the dashboard HTML. Connectors run on a schedule and write into SQLite."""
import time, os, logging, threading
from fastapi import FastAPI, Body
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from . import store, scheduler
from .connectors import homeassistant as ha
from .connectors import health as health_parser

INGEST_TOKEN = os.environ.get("HEALTH_INGEST_TOKEN", "").strip()

logging.basicConfig(level=logging.INFO)
app = FastAPI(title="myLife", version="0.1.0")
_sched = None

@app.on_event("startup")
def _startup():
    global _sched
    _sched = scheduler.start()

@app.get("/api/health")
def health():
    return {"ok": True, "ts": time.time()}

@app.post("/api/refresh")
def refresh(source: str = "home"):
    """Force an immediate pull. ?source=home|shopping|all. Returns fresh age."""
    try:
        if source in ("home", "all"): scheduler.pull_home()
        if source in ("shopping", "all"): scheduler.pull_shopping()
        snap = store.get("home")
        age = round(time.time() - snap["updated_at"]) if snap else None
        return JSONResponse({"ok": True, "refreshed": source, "home_age_seconds": age})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=502)

@app.post("/api/health/ingest")
def ingest_health(payload: dict = Body(...), token: str = ""):
    """Receives the iOS Health Auto Export POST. Optional ?token= guard so only
    your phone can push. Stores a normalized health snapshot."""
    if INGEST_TOKEN and token != INGEST_TOKEN:
        return JSONResponse({"error": "invalid token"}, status_code=401)
    try:
        snap = health_parser.parse(payload)
        store.put("health", snap)
        return JSONResponse({"ok": True, "stored": list(snap.keys())})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)

def _patch_light_state(entity_id, on=None, brightness=None):
    """Optimistically update the stored home snapshot's light list so the UI
    doesn't flicker back before HA reports the new state."""
    snap = store.get("home")
    if not snap: return
    home = snap["data"]; lights = home.get("lights", {})
    lst = lights.get("list", [])
    changed = False
    for l in lst:
        if l.get("entity_id") == entity_id:
            if brightness is not None:
                l["brightness"] = int(brightness); l["on"] = int(brightness) > 0
            elif on is not None:
                l["on"] = bool(on)
            changed = True
    if changed:
        lights["on"] = sum(1 for l in lst if l.get("on"))
        lights["on_names"] = [l["name"] for l in lst if l.get("on")]
        store.put("home", home)

@app.post("/api/light")
def control_light(payload: dict = Body(...)):
    """Control a light. Body: {entity_id, on?:bool, brightness?:0-100}.
    Scoped to light.* only by the connector."""
    entity_id = payload.get("entity_id", "")
    on = payload.get("on")
    brightness = payload.get("brightness")
    try:
        result = ha.set_light(entity_id, on=on, brightness_pct=brightness)
        # HA accepted the command -> patch the stored snapshot to the intended
        # state so the client's immediate re-fetch shows it (no flicker-back).
        try: _patch_light_state(entity_id, on=on, brightness=brightness)
        except Exception: pass
        # Reconcile with HA ground truth in the BACKGROUND after Hue has settled
        # (~6s). Non-blocking, so it never races the client's read or hangs the
        # request. The normal 180s poll is the ongoing source of truth.
        try:
            threading.Timer(6.0, scheduler.pull_home).start()
        except Exception: pass
        return JSONResponse(result)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=502)

@app.get("/api/dashboard")
def dashboard():
    """One clean feed the dashboard consumes. Stitches every connector's
    latest snapshot + freshness so the UI can show 'live / stale'."""
    sources = store.all_sources()
    out = {"generated_at": time.time(), "panels": {}, "freshness": {}}
    for name in ("home", "shopping", "health", "finance", "calendar"):
        snap = sources.get(name)
        if snap:
            out["panels"][name] = snap["data"]
            out["freshness"][name] = {
                "updated_at": snap["updated_at"],
                "age_seconds": round(time.time() - snap["updated_at"]),
            }
        err = sources.get(name + ":error")
        if err:
            out["freshness"].setdefault(name, {})["error"] = err["data"].get("error")
    return JSONResponse(out)

@app.get("/api/{source}")
def one(source: str):
    snap = store.get(source)
    if not snap:
        return JSONResponse({"error": "no data yet"}, status_code=404)
    return JSONResponse(snap)

# --- serve the dashboard UI ---
UI = os.path.join(os.path.dirname(__file__), "static", "index.html")

@app.get("/", response_class=HTMLResponse)
def root():
    if os.path.exists(UI):
        return FileResponse(UI)
    return HTMLResponse("<h1>myLife backend running</h1>"
                        "<p>Dashboard UI not bundled. See <a href='/api/dashboard'>/api/dashboard</a>.</p>")

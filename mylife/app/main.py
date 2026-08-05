"""myLife backend — FastAPI. Serves the aggregated /api/dashboard feed and
the dashboard HTML. Connectors run on a schedule and write into SQLite."""
import time, os, logging
from fastapi import FastAPI
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from . import store, scheduler

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

@app.get("/api/dashboard")
def dashboard():
    """One clean feed the dashboard consumes. Stitches every connector's
    latest snapshot + freshness so the UI can show 'live / stale'."""
    sources = store.all_sources()
    out = {"generated_at": time.time(), "panels": {}, "freshness": {}}
    for name in ("home", "shopping", "finance", "calendar"):
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

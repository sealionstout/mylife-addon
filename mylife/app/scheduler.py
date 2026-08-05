"""APScheduler timers: pull HA frequently, BL101 daily. Each pull is wrapped
so one connector failing never takes down the others."""
import os, logging, traceback
from apscheduler.schedulers.background import BackgroundScheduler
from .connectors import homeassistant, bl101
from . import store

log = logging.getLogger("mylife.scheduler")

HA_SECS = int(os.environ.get("HA_POLL_SECONDS", "180"))
BL_HOURS = int(os.environ.get("BL101_POLL_HOURS", "24"))

def _safe(name, fn):
    try:
        data = fn()
        store.put(name, data)
        log.info("pulled %s ok", name)
    except Exception as e:
        log.error("pull %s FAILED: %s\n%s", name, e, traceback.format_exc())
        # record the error so the API/dashboard can show 'stale/failed'
        store.put(name + ":error", {"error": str(e)})

def pull_home():     _safe("home", homeassistant.pull)
def pull_shopping(): _safe("shopping", bl101.pull)

def start():
    sched = BackgroundScheduler(timezone="UTC")
    sched.add_job(pull_home, "interval", seconds=HA_SECS, id="home", next_run_time=None)
    sched.add_job(pull_shopping, "interval", hours=BL_HOURS, id="shopping", next_run_time=None)
    sched.start()
    # prime immediately on boot
    pull_home(); pull_shopping()
    return sched

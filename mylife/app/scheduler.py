"""APScheduler timers: pull HA frequently, BL101 daily. Hardened so a slow,
hung, or failing pull can never permanently stall the schedule."""
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
        # clear any prior error marker on success
        store.put(name + ":error", {"error": None})
        log.info("pulled %s ok", name)
    except Exception as e:
        log.error("pull %s FAILED: %s\n%s", name, e, traceback.format_exc())
        store.put(name + ":error", {"error": str(e)})

def pull_home():     _safe("home", homeassistant.pull)
def pull_shopping(): _safe("shopping", bl101.pull)

def start():
    # Job defaults that prevent a slow/overlapping run from wedging the schedule:
    #  - coalesce: collapse missed runs into one
    #  - max_instances 1 + misfire_grace_time: skip-but-keep-scheduling if a run is late
    sched = BackgroundScheduler(
        timezone="UTC",
        job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": 120},
    )
    sched.add_job(pull_home, "interval", seconds=HA_SECS, id="home",
                  replace_existing=True)
    sched.add_job(pull_shopping, "interval", hours=BL_HOURS, id="shopping",
                  replace_existing=True)
    sched.start()
    # prime immediately on boot
    pull_home()
    pull_shopping()
    log.info("scheduler started: home every %ss, shopping every %sh", HA_SECS, BL_HOURS)
    return sched

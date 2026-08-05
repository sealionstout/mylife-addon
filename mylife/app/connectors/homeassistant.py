"""Home Assistant connector — reads /api/states via the Supervisor proxy.
In the add-on, HA_URL=http://supervisor/core and SUPERVISOR_TOKEN is injected."""
import os, requests

HA_URL = os.environ.get("HA_URL", "http://supervisor/core").rstrip("/")
TOKEN = os.environ.get("SUPERVISOR_TOKEN") or os.environ.get("HA_TOKEN", "")

def _fetch_states():
    # Dev fallback: read a saved /api/states dump instead of hitting HA live.
    dev_file = os.environ.get("HA_STATES_FILE")
    if dev_file and os.path.exists(dev_file):
        import json
        with open(dev_file) as f:
            return json.load(f)
    # (connect, read) timeouts so a hung socket can never stall the scheduler
    r = requests.get(f"{HA_URL}/api/states",
                     headers={"Authorization": f"Bearer {TOKEN}"}, timeout=(5, 15))
    r.raise_for_status()
    return r.json()

def _fnum(v):
    try: return float(v)
    except (TypeError, ValueError): return None

def call_service(domain, service, entity_id, extra=None):
    """Call an HA service (e.g. light.turn_on) via the Supervisor proxy."""
    data = {"entity_id": entity_id}
    if extra: data.update(extra)
    r = requests.post(f"{HA_URL}/api/services/{domain}/{service}",
                      headers={"Authorization": f"Bearer {TOKEN}",
                               "Content-Type": "application/json"},
                      json=data, timeout=(5, 12))
    r.raise_for_status()
    return {"ok": True, "entity_id": entity_id, "service": f"{domain}.{service}"}

LIGHT_PREFIX = "light."

def set_light(entity_id, on=None, brightness_pct=None):
    """Turn a light on/off and/or set brightness (0-100). Guarded to light.* only."""
    if not entity_id.startswith(LIGHT_PREFIX):
        raise ValueError("only light.* entities may be controlled")
    if brightness_pct is not None:
        pct = max(0, min(100, int(brightness_pct)))
        if pct == 0:
            return call_service("light", "turn_off", entity_id)
        return call_service("light", "turn_on", entity_id, {"brightness_pct": pct})
    if on is True:
        return call_service("light", "turn_on", entity_id)
    if on is False:
        return call_service("light", "turn_off", entity_id)
    return call_service("light", "toggle", entity_id)

def normalize(states):
    by_id = {s["entity_id"]: s for s in states}
    def attr(eid, k, d=None):
        s = by_id.get(eid); return s["attributes"].get(k, d) if s else d

    # --- climate (thermostat) ---
    climate = None
    for s in states:
        if s["entity_id"].startswith("climate."):
            a = s["attributes"]
            climate = {"name": a.get("friendly_name"), "mode": s["state"],
                       "current": a.get("current_temperature"),
                       "target": a.get("temperature"),
                       "humidity": a.get("current_humidity"),
                       "action": a.get("hvac_action")}
            break

    # --- lights (room/zone groups: full list + on count) ---
    groups = [s for s in states if s["entity_id"].startswith("light.")
              and s["attributes"].get("is_hue_group")]
    light_list = []
    for s in groups:
        a = s["attributes"]
        br = a.get("brightness")
        light_list.append({
            "entity_id": s["entity_id"],
            "name": a.get("friendly_name"),
            "on": s["state"] == "on",
            "brightness": round(br / 255 * 100) if br else None,
        })
    # on first, then alphabetical
    light_list.sort(key=lambda x: (not x["on"], (x["name"] or "").lower()))
    lights_on = [l["name"] for l in light_list if l["on"]]
    lights = {"total": len(groups), "on": len(lights_on),
              "on_names": lights_on, "list": light_list}

    # --- security: doors + alarm ---
    doors = [s for s in states if s["entity_id"].startswith("binary_sensor.")
             and s["attributes"].get("device_class") == "door"]
    open_doors = [s["attributes"].get("friendly_name") for s in doors if s["state"] == "on"]
    alarm = next((s for s in states if s["entity_id"].startswith("alarm_control_panel.")), None)
    security = {"alarm_state": alarm["state"] if alarm else None,
                "doors_total": len(doors), "doors_open": len(open_doors),
                "open_names": open_doors}

    # --- presence ---
    person = next((s for s in states if s["entity_id"].startswith("person.")), None)
    presence = {"state": person["state"] if person else None}

    # --- weather ---
    w = next((s for s in states if s["entity_id"].startswith("weather.")), None)
    weather = None
    if w:
        weather = {"condition": w["state"], "temp": w["attributes"].get("temperature"),
                   "humidity": w["attributes"].get("humidity")}

    # --- cameras ---
    cams = [s for s in states if s["entity_id"].startswith("camera.")
            and s["state"] in ("streaming", "idle", "recording")]

    # --- alerts: low battery + low ink ---
    alerts = []
    for s in states:
        a = s["attributes"]
        if a.get("device_class") == "battery" and a.get("unit_of_measurement") == "%":
            lvl = _fnum(s["state"])
            if lvl is not None and lvl <= 15:
                alerts.append({"type": "battery", "name": a.get("friendly_name"), "level": lvl})
        if a.get("marker_type") == "ink-cartridge":
            lvl = _fnum(s["state"])
            if lvl is not None and lvl <= (a.get("marker_low_level") or 15):
                alerts.append({"type": "ink", "name": a.get("friendly_name"), "level": lvl})
    if security["doors_open"] and security["alarm_state"] == "disarmed" and presence["state"] == "not_home":
        alerts.append({"type": "security",
                       "name": f"{security['open_names'][0]} open while away & disarmed", "level": 0})

    return {"climate": climate, "lights": lights, "security": security,
            "presence": presence, "weather": weather,
            "cameras": len(cams), "alerts": alerts}

def pull():
    return normalize(_fetch_states())

if __name__ == "__main__":
    import json
    print(json.dumps(pull(), indent=2))

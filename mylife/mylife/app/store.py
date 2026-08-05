"""Tiny SQLite store: latest snapshot per connector + append-only history."""
import sqlite3, json, os, time, threading

DB_PATH = os.environ.get("DB_PATH", "/share/mylife.db")
_lock = threading.Lock()

def _conn():
    c = sqlite3.connect(DB_PATH)
    c.execute("""CREATE TABLE IF NOT EXISTS snapshots(
        source TEXT PRIMARY KEY, payload TEXT, updated_at REAL)""")
    c.execute("""CREATE TABLE IF NOT EXISTS history(
        id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT,
        payload TEXT, ts REAL)""")
    return c

def put(source: str, payload: dict):
    with _lock, _conn() as c:
        now = time.time()
        c.execute("REPLACE INTO snapshots(source,payload,updated_at) VALUES(?,?,?)",
                  (source, json.dumps(payload), now))
        c.execute("INSERT INTO history(source,payload,ts) VALUES(?,?,?)",
                  (source, json.dumps(payload), now))
        # keep history bounded (last 2000 rows per source is plenty)
        c.execute("""DELETE FROM history WHERE source=? AND id NOT IN
                     (SELECT id FROM history WHERE source=? ORDER BY id DESC LIMIT 2000)""",
                  (source, source))

def get(source: str):
    with _lock, _conn() as c:
        row = c.execute("SELECT payload,updated_at FROM snapshots WHERE source=?",
                        (source,)).fetchone()
        if not row: return None
        return {"data": json.loads(row[0]), "updated_at": row[1]}

def all_sources():
    with _lock, _conn() as c:
        rows = c.execute("SELECT source,payload,updated_at FROM snapshots").fetchall()
        return {r[0]: {"data": json.loads(r[1]), "updated_at": r[2]} for r in rows}

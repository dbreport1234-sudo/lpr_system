import os
import sqlite3
import threading
import time

CAM_FIELDS = ("name", "ip", "username", "password", "rtsp_port", "http_port", "stream_path",
              "url_encode", "brand", "direction", "enabled", "gate_enabled", "do_channel")


class Storage:
    def __init__(self, db_path, image_dir):
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        os.makedirs(image_dir, exist_ok=True)
        self.image_dir = image_dir
        self._lock = threading.Lock()
        self.db = sqlite3.connect(db_path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL NOT NULL,
  plate TEXT NOT NULL, province TEXT, conf REAL, track_id INTEGER, votes INTEGER,
  full_image TEXT, plate_image TEXT, authorized INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS cameras(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, ip TEXT,
  username TEXT, password TEXT, rtsp_port INTEGER DEFAULT 554, http_port INTEGER DEFAULT 80,
  stream_path TEXT DEFAULT '/live1s1.sdp', url_encode INTEGER DEFAULT 1, brand TEXT DEFAULT 'vivotek', direction TEXT DEFAULT 'both',
  enabled INTEGER DEFAULT 1, gate_enabled INTEGER DEFAULT 0, do_channel INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS plates(plate TEXT PRIMARY KEY, kind TEXT, owner TEXT, note TEXT);
CREATE INDEX IF NOT EXISTS ix_plate ON events(plate);
CREATE INDEX IF NOT EXISTS ix_ts ON events(ts);""")
        for col in ("camera_id INTEGER", "list_type TEXT"):  # migrate จากเวอร์ชันเก่า
            try:
                self.db.execute(f"ALTER TABLE events ADD COLUMN {col}")
            except sqlite3.OperationalError:
                pass
        try:
            self.db.execute("ALTER TABLE cameras ADD COLUMN brand TEXT DEFAULT 'vivotek'")
        except sqlite3.OperationalError:
            pass
        self.db.commit()

    def _q(self, sql, args=()):
        with self._lock:
            return [dict(r) for r in self.db.execute(sql, args).fetchall()]

    def _x(self, sql, args=()):
        with self._lock:
            cur = self.db.execute(sql, args)
            self.db.commit()
            return cur.lastrowid

    # ---- events ----
    def add(self, **kw):
        return self._x(
            "INSERT INTO events(ts,plate,province,conf,track_id,votes,full_image,plate_image,authorized,camera_id,list_type)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (kw.get("ts", time.time()), kw["plate"], kw.get("province"), kw.get("conf"), kw.get("track_id"),
             kw.get("votes"), kw.get("full_image"), kw.get("plate_image"), int(kw.get("authorized", False)),
             kw.get("camera_id"), kw.get("list_type")))

    @staticmethod
    def _where(plate=None, camera_id=None, start=None, end=None, kind=None):
        w, a = [], []
        if plate:
            w.append("plate LIKE ?"); a.append("%" + plate.replace("*", "%") + "%")
        if camera_id:
            w.append("camera_id=?"); a.append(camera_id)
        if start:
            w.append("ts>=?"); a.append(start)
        if end:
            w.append("ts<?"); a.append(end)
        if kind:
            if kind == "unknown":
                w.append("list_type IS NULL")
            else:
                w.append("list_type=?"); a.append(kind)
        return (" WHERE " + " AND ".join(w)) if w else "", a

    def list(self, limit=50, offset=0, **f):
        w, a = self._where(**f)
        return self._q(f"SELECT * FROM events{w} ORDER BY id DESC LIMIT ? OFFSET ?", a + [limit, offset])

    def get(self, event_id):
        r = self._q("SELECT * FROM events WHERE id=?", (event_id,))
        return r[0] if r else None

    def report(self, start, end):
        w, a = self._where(start=start, end=end)
        d = "strftime('%Y-%m-%d',ts,'unixepoch','localtime')"
        h = "strftime('%H',ts,'unixepoch','localtime')"
        return {
            "total": self._q(f"SELECT COUNT(*) n, COUNT(DISTINCT plate) u FROM events{w}", a)[0],
            "by_day": self._q(f"SELECT {d} k, COUNT(*) n FROM events{w} GROUP BY k ORDER BY k", a),
            "by_hour": self._q(f"SELECT {h} k, COUNT(*) n FROM events{w} GROUP BY k ORDER BY k", a),
            "by_camera": self._q(f"SELECT camera_id k, COUNT(*) n, COUNT(DISTINCT plate) u FROM events{w} GROUP BY k", a),
            "by_kind": self._q(f"SELECT COALESCE(list_type,'unknown') k, COUNT(*) n FROM events{w} GROUP BY k", a),
            "top": self._q(f"SELECT plate k, COUNT(*) n FROM events{w} GROUP BY plate ORDER BY n DESC LIMIT 10", a),
        }

    # ---- cameras ----
    def cameras(self):
        return self._q("SELECT * FROM cameras ORDER BY id")

    def camera(self, cid):
        r = self._q("SELECT * FROM cameras WHERE id=?", (cid,))
        return r[0] if r else None

    def save_camera(self, data, cid=None):
        d = {k: data[k] for k in CAM_FIELDS if k in data}
        if cid:
            if not d.get("password"):
                d.pop("password", None)  # ไม่ส่งมา = คงรหัสเดิม
            if d:
                self._x(f"UPDATE cameras SET {','.join(k + '=?' for k in d)} WHERE id=?", list(d.values()) + [cid])
            return cid
        return self._x(f"INSERT INTO cameras({','.join(d)}) VALUES({','.join('?' * len(d))})", list(d.values()))

    def delete_camera(self, cid):
        self._x("DELETE FROM cameras WHERE id=?", (cid,))

    # ---- whitelist / blacklist ----
    def plates(self):
        return self._q("SELECT * FROM plates ORDER BY plate")

    def save_plate(self, plate, kind, owner="", note=""):
        self._x("INSERT OR REPLACE INTO plates VALUES(?,?,?,?)", (plate.replace(" ", ""), kind, owner, note))

    def delete_plate(self, plate):
        self._x("DELETE FROM plates WHERE plate=?", (plate,))

    def lookup(self, plate):
        r = self._q("SELECT kind FROM plates WHERE plate=?", (plate,))
        return r[0]["kind"] if r else None

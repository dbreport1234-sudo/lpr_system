import csv
import io
import os
import time
from datetime import datetime, timedelta

from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse, Response, StreamingResponse

WEB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web", "index.html")


def _ts(day, plus=0):
    if not day:
        return None
    return (datetime.strptime(day, "%Y-%m-%d") + timedelta(days=plus)).timestamp()


def create_app(storage, mgr):
    app = FastAPI(title="Thai LPR")

    def cam_public(r):
        d = {k: v for k, v in r.items() if k != "password"}
        d["has_password"] = bool(r.get("password"))
        d.update(mgr.status(r["id"]))
        return d

    def filt(plate, camera_id, start, end, kind):
        return dict(plate=plate or None, camera_id=camera_id or None, start=_ts(start), end=_ts(end, 1), kind=kind or None)

    @app.get("/", response_class=HTMLResponse)
    def index():
        return open(WEB, encoding="utf-8").read()

    @app.get("/health")
    def health():
        return {"status": "ok"}

    # ---- กล้อง ----
    @app.get("/api/cameras")
    def cameras():
        return [cam_public(r) for r in storage.cameras()]

    @app.post("/api/cameras")
    def add_camera(data: dict = Body(...)):
        cid = storage.save_camera(data)
        mgr.start(cid)
        return {"id": cid}

    @app.put("/api/cameras/{cid}")
    def edit_camera(cid: int, data: dict = Body(...)):
        if not storage.camera(cid):
            raise HTTPException(404)
        storage.save_camera(data, cid)
        mgr.restart(cid)
        return {"id": cid}

    @app.delete("/api/cameras/{cid}")
    def del_camera(cid: int):
        mgr.stop(cid)
        storage.delete_camera(cid)
        return {"ok": True}

    @app.post("/api/cameras/{cid}/open-gate")
    def open_gate(cid: int):
        if not mgr.open_gate(cid):
            raise HTTPException(400, "กล้องนี้ไม่ได้เปิดใช้งานการควบคุมประตู")
        return {"ok": True}

    @app.get("/api/cameras/{cid}/snapshot")
    def snapshot(cid: int):
        j = mgr.jpeg(cid)
        if not j:
            raise HTTPException(404, "ยังไม่มีภาพ")
        return Response(j, media_type="image/jpeg", headers={"Cache-Control": "no-store"})

    @app.get("/api/cameras/{cid}/stream")
    def stream(cid: int):
        def gen():
            last = None
            while True:
                j = mgr.jpeg(cid)
                if j is not None and j is not last:
                    last = j
                    yield b"--f\r\nContent-Type: image/jpeg\r\nContent-Length: %d\r\n\r\n" % len(j) + j + b"\r\n"
                time.sleep(0.1)
        return StreamingResponse(gen(), media_type="multipart/x-mixed-replace; boundary=f")

    # ---- เหตุการณ์ ----
    @app.get("/api/events")
    def events(plate: str = "", camera_id: int = 0, start: str = "", end: str = "", kind: str = "",
               limit: int = 100, offset: int = 0):
        return storage.list(min(limit, 500), offset, **filt(plate, camera_id, start, end, kind))

    @app.get("/api/events/export.csv")
    def export(plate: str = "", camera_id: int = 0, start: str = "", end: str = "", kind: str = ""):
        names = {c["id"]: c["name"] for c in storage.cameras()}
        rows = storage.list(100000, 0, **filt(plate, camera_id, start, end, kind))
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["id", "เวลา", "ทะเบียน", "จังหวัด", "กล้อง", "ความมั่นใจ", "รายการ"])
        for r in rows:
            w.writerow([r["id"], datetime.fromtimestamp(r["ts"]).strftime("%Y-%m-%d %H:%M:%S"), r["plate"],
                        r["province"] or "", names.get(r["camera_id"], ""), round(r["conf"] or 0, 2), r["list_type"] or ""])
        data = "\ufeff" + buf.getvalue()  # BOM ให้ Excel อ่านภาษาไทยถูก
        return Response(data, media_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": "attachment; filename=lpr_events.csv"})

    @app.get("/events/{eid}/image")
    def image(eid: int, kind: str = "full"):
        e = storage.get(eid)
        if not e:
            raise HTTPException(404)
        path = os.path.join(storage.image_dir, e["plate_image"] if kind == "plate" else e["full_image"])
        if not os.path.isfile(path):
            raise HTTPException(404)
        return FileResponse(path, media_type="image/jpeg")

    # ---- รายงาน ----
    @app.get("/api/report")
    def report(start: str = "", end: str = ""):
        r = storage.report(_ts(start), _ts(end, 1))
        names = {c["id"]: c["name"] for c in storage.cameras()}
        for x in r["by_camera"]:
            x["name"] = names.get(x["k"], "(ถูกลบ)")
        return r

    # ---- รายการทะเบียน ----
    @app.get("/api/plates")
    def plates():
        return storage.plates()

    @app.post("/api/plates")
    def add_plate(data: dict = Body(...)):
        if not data.get("plate") or data.get("kind") not in ("white", "black"):
            raise HTTPException(400, "ต้องระบุทะเบียนและประเภท (white/black)")
        storage.save_plate(data["plate"], data["kind"], data.get("owner", ""), data.get("note", ""))
        return {"ok": True}

    @app.delete("/api/plates/{plate}")
    def del_plate(plate: str):
        storage.delete_plate(plate)
        return {"ok": True}

    return app

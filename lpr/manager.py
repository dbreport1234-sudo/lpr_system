"""จัดการกล้องหลายตัว: 1 กล้อง = reader + YOLO/tracker ของตัวเอง + pipeline 1 เธรด  (OCR ใช้ร่วมกันผ่าน lock)"""
import logging
import threading

from .camera import RTSPCamera
from .config import build_rtsp_url
from .detector import PlateDetector
from .gate import VivotekGate
from .pipeline import Pipeline

log = logging.getLogger("lpr.manager")


class SharedOCR:
    def __init__(self, ocr):
        self.ocr, self.lock = ocr, threading.Lock()

    def read(self, crop):
        with self.lock:
            return self.ocr.read(crop)


class Manager:
    def __init__(self, cfg, storage, ocr):
        self.cfg, self.storage, self.ocr = cfg, storage, SharedOCR(ocr)
        self.workers = {}

    def start(self, cid):
        row = self.storage.camera(cid)
        if not row or not row["enabled"] or cid in self.workers:
            return
        url = build_rtsp_url(row["username"], row["password"], row["ip"], row["rtsp_port"],
                             row["stream_path"], bool(row["url_encode"]))
        d = self.cfg["detector"]
        cam = RTSPCamera(url, self.cfg["camera"]["reconnect_delay"]).start()
        det = PlateDetector(d["weights"], d["conf"], d["imgsz"], d["device"], d["tracker"], d.get("classes"))
        g = self.cfg["gate"]
        host = row["ip"] if row["http_port"] == 80 else f"{row['ip']}:{row['http_port']}"
        gate = VivotekGate(host, row["username"], row["password"], row["do_channel"], g["open_ms"],
                           g["cooldown_sec"], g.get("scheme", "http")) if row["gate_enabled"] and row.get("brand", "vivotek") == "vivotek" else None  # สั่ง DO รองรับเฉพาะ Vivotek
        pipe = Pipeline(self.cfg, cam, det, self.ocr, self.storage, gate, row["id"], row["name"])
        threading.Thread(target=pipe.run, daemon=True, name=f"pipe-{cid}").start()
        self.workers[cid] = (cam, pipe, gate)
        log.info("เริ่มกล้อง %s (%s)", row["name"], row["ip"])

    def stop(self, cid):
        w = self.workers.pop(cid, None)
        if w:
            w[0].stop(); w[1].stop()

    def restart(self, cid):
        self.stop(cid)
        self.start(cid)

    def start_all(self):
        for r in self.storage.cameras():
            threading.Thread(target=self.start, args=(r["id"],), daemon=True).start()

    def status(self, cid):
        import time
        w = self.workers.get(cid)
        if not w:
            return {"state": "stopped", "fps": 0}
        cam, pipe, _ = w
        live = time.time() - pipe.last_frame_ts < 10
        return {"state": "online" if cam.connected and live else "offline", "fps": round(pipe.fps, 1)}

    def jpeg(self, cid):
        w = self.workers.get(cid)
        return w[1].jpeg if w else None

    def open_gate(self, cid):
        w = self.workers.get(cid)
        if not w or not w[2]:
            return False
        w[2].open_async()
        return True

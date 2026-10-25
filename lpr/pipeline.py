"""Pipeline หลัก: frame -> detect+track -> OCR ต่อ track -> voting -> บันทึก/เปิดประตู"""
import logging
import os
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

import cv2
import numpy as np

log = logging.getLogger("lpr.pipeline")


@dataclass
class Track:
    first_seen: float
    last_seen: float
    frames: int = 0
    ocr_runs: int = 0
    weight: dict = field(default_factory=lambda: defaultdict(float))
    count: dict = field(default_factory=lambda: defaultdict(int))
    prov: dict = field(default_factory=lambda: defaultdict(float))
    best_q: float = 0.0
    best_crop: Optional[np.ndarray] = None
    best_frame: Optional[np.ndarray] = None
    best_box: Optional[tuple] = None
    emitted: bool = False


class Pipeline:
    def __init__(self, cfg, camera, detector, ocr, storage, gate=None, cam_id=None, cam_name=""):
        self.cfg, self.cam, self.det, self.ocr = cfg, camera, detector, ocr
        self.storage, self.gate, self.cam_id, self.cam_name = storage, gate, cam_id, cam_name
        self.jpeg, self.fps, self.last_frame_ts, self._fc, self._ft = None, 0.0, 0.0, 0, time.time()
        t = cfg["tracking"]
        self.min_w = t["min_plate_width_px"]
        self.ocr_every = t["ocr_every_n_frames"]
        self.max_ocr = t["max_ocr_per_track"]
        self.confirm_votes = t["confirm_votes"]
        self.lost_min_votes = t["lost_min_votes"]
        self.max_age = t["max_age_sec"]
        self.dedupe = t["dedupe_sec"]
        self.roi = cfg.get("roi")
        self.tracks: dict[int, Track] = {}
        self._recent: dict[str, float] = {}
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()

    # ---------- helpers ----------
    def _in_roi(self, box, shape):
        if not self.roi:
            return True
        h, w = shape[:2]
        cx, cy = (box[0] + box[2]) / 2 / w, (box[1] + box[3]) / 2 / h
        x1, y1, x2, y2 = self.roi
        return x1 <= cx <= x2 and y1 <= cy <= y2

    def _save(self, tr: Track, ts: float, tid: int):
        day = time.strftime("%Y%m%d", time.localtime(ts))
        folder = os.path.join(self.storage.image_dir, day)
        os.makedirs(folder, exist_ok=True)
        base = f"{int(ts * 1000)}_{tid}"
        full_p = os.path.join(folder, base + "_full.jpg")
        plate_p = os.path.join(folder, base + "_plate.jpg")
        full = tr.best_frame.copy()
        x1, y1, x2, y2 = tr.best_box
        cv2.rectangle(full, (x1, y1), (x2, y2), (0, 255, 0), 4)
        if full.shape[1] > 1920:
            s = 1920 / full.shape[1]
            full = cv2.resize(full, None, fx=s, fy=s)
        cv2.imwrite(full_p, full, [cv2.IMWRITE_JPEG_QUALITY, 85])
        cv2.imwrite(plate_p, tr.best_crop, [cv2.IMWRITE_JPEG_QUALITY, 95])
        rel = lambda p: os.path.relpath(p, self.storage.image_dir)  # noqa: E731
        return rel(full_p), rel(plate_p)

    def _finalize(self, tid: int, tr: Track, reason: str):
        if tr.emitted or not tr.weight or tr.best_crop is None:
            return
        plate = max(tr.weight, key=tr.weight.get)
        votes = tr.count[plate]
        conf = tr.weight[plate] / votes
        province = max(tr.prov, key=tr.prov.get) if tr.prov else None
        tr.emitted = True
        now = time.time()
        if now - self._recent.get(plate, 0) < self.dedupe:
            return
        self._recent[plate] = now
        full_img, plate_img = self._save(tr, now, tid)
        kind = self.storage.lookup(plate)
        authorized = kind == "white"
        eid = self.storage.add(ts=now, plate=plate, province=province, conf=conf,
                               track_id=tid, votes=votes, full_image=full_img,
                               plate_image=plate_img, authorized=authorized,
                               camera_id=self.cam_id, list_type=kind)
        log.info("[%s][cam %s] #%d %s %s conf=%.2f votes=%d list=%s",
                 reason, self.cam_id, eid, plate, province or "-", conf, votes, kind)
        if authorized and self.gate:
            self.gate.open_async()

    def _annotate(self, frame, dets):
        """ภาพสดสำหรับ UI: ย่อเหลือกว้าง ≤960 พร้อมกรอบป้าย"""
        h, w = frame.shape[:2]
        sc = 960 / w if w > 960 else 1.0
        img = cv2.resize(frame, None, fx=sc, fy=sc) if sc < 1 else frame.copy()
        for d in dets:
            x1, y1, x2, y2 = [int(v * sc) for v in d.box]
            cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(img, f"#{d.track_id}", (x1, max(15, y1 - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 70])
        if ok:
            self.jpeg = buf.tobytes()
        self._fc += 1
        t = time.time()
        if t - self._ft >= 3:
            self.fps, self._fc, self._ft = self._fc / (t - self._ft), 0, t
        self.last_frame_ts = t

    # ---------- main loop ----------
    def run(self):
        last_id = -1
        while not self._stop.is_set():
            item = self.cam.read(last_id)
            if item is None:
                time.sleep(0.005)
                continue
            last_id, frame, ts = item
            try:
                self._process(frame, ts)
            except Exception:  # noqa: BLE001
                log.exception("เกิดข้อผิดพลาดใน pipeline")

    def _process(self, frame, ts):
        now = time.time()
        dets = self.det.track(frame)
        for d in dets:
            x1, y1, x2, y2 = d.box
            h, w = frame.shape[:2]
            x1, y1, x2, y2 = max(0, x1), max(0, y1), min(w, x2), min(h, y2)
            if x2 - x1 < self.min_w or not self._in_roi((x1, y1, x2, y2), frame.shape):
                continue
            tr = self.tracks.get(d.track_id)
            if tr is None:
                tr = self.tracks[d.track_id] = Track(first_seen=now, last_seen=now)
            tr.last_seen = now
            tr.frames += 1
            crop = frame[y1:y2, x1:x2]
            if crop.size == 0 or tr.emitted:
                continue

            # เก็บเฟรมที่คมและป้ายใหญ่ที่สุดไว้เป็นหลักฐาน
            sharp = cv2.Laplacian(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var()
            q = sharp * (x2 - x1)
            if q > tr.best_q:
                tr.best_q, tr.best_crop = q, crop.copy()
                tr.best_frame, tr.best_box = frame, (x1, y1, x2, y2)

            if tr.ocr_runs >= self.max_ocr or tr.frames % self.ocr_every:
                continue
            tr.ocr_runs += 1
            res = self.ocr.read(crop)
            if not res:
                continue
            plate, province, conf = res
            tr.weight[plate] += conf
            tr.count[plate] += 1
            if province:
                tr.prov[province] += conf
            top = max(tr.weight, key=tr.weight.get)
            if tr.count[top] >= self.confirm_votes:
                self._finalize(d.track_id, tr, "confirmed")

        self._annotate(frame, dets)
        # ปิด track ที่หายไปแล้ว
        for tid in [t for t, s in self.tracks.items() if now - s.last_seen > self.max_age]:
            tr = self.tracks.pop(tid)
            if not tr.emitted and tr.weight:
                top = max(tr.weight, key=tr.weight.get)
                if tr.count[top] >= self.lost_min_votes:
                    self._finalize(tid, tr, "lost")

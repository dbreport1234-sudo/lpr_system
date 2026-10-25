"""อ่าน RTSP จาก Vivotek แบบ thread เดียว เก็บเฉพาะเฟรมล่าสุด (ลด latency) + reconnect อัตโนมัติ"""
import logging
import os
import threading
import time

# ต้องตั้งก่อน import cv2: ใช้ TCP กันแพ็กเก็ตหาย + ลด buffer
os.environ.setdefault(
    "OPENCV_FFMPEG_CAPTURE_OPTIONS",
    "rtsp_transport;tcp|fflags;nobuffer|flags;low_delay|stimeout;5000000",
)
import cv2  # noqa: E402

log = logging.getLogger("lpr.camera")


class RTSPCamera:
    def __init__(self, url: str, reconnect_delay: float = 5.0):
        self.url = url
        self.reconnect_delay = reconnect_delay
        self._lock = threading.Lock()
        self._frame = None
        self._id = 0
        self._ts = 0.0
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True, name="camera")
        self.connected = False

    def start(self):
        self._thread.start()
        return self

    def stop(self):
        self._stop.set()

    def read(self, last_id: int = -1):
        """คืน (frame_id, frame, ts) ถ้ามีเฟรมใหม่กว่า last_id ไม่งั้นคืน None"""
        with self._lock:
            if self._frame is None or self._id == last_id:
                return None
            return self._id, self._frame, self._ts

    def _run(self):
        while not self._stop.is_set():
            cap = cv2.VideoCapture(self.url, cv2.CAP_FFMPEG)
            if not cap.isOpened():
                self.connected = False
                log.warning("เปิดสตรีมไม่ได้ จะลองใหม่ใน %.0fs", self.reconnect_delay)
                time.sleep(self.reconnect_delay)
                continue
            log.info("เชื่อมต่อกล้องสำเร็จ")
            self.connected = True
            fails = 0
            while not self._stop.is_set():
                ok, frame = cap.read()
                if not ok:
                    fails += 1
                    if fails > 30:
                        break
                    time.sleep(0.05)
                    continue
                fails = 0
                with self._lock:
                    self._frame = frame
                    self._id += 1
                    self._ts = time.time()
            cap.release()
            self.connected = False
            log.warning("สตรีมหลุด กำลัง reconnect")
            time.sleep(self.reconnect_delay)

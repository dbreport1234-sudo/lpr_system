"""สั่ง Digital Output ของกล้อง Vivotek เพื่อเปิดไม้กั้น/ประตู
หมายเหตุ: URL ด้านล่างอ้างอิง Vivotek URL Command (dido/setdo.cgi) ให้ตรวจกับเฟิร์มแวร์ของกล้องคุณก่อนใช้งานจริง
และต้องตั้งค่า DO ในหน้าเว็บกล้อง (Configuration > Peripheral > DI/DO) ให้ตรงกับรีเลย์ที่ต่ออยู่"""
import logging
import threading
import time

import requests
from requests.auth import HTTPBasicAuth, HTTPDigestAuth

log = logging.getLogger("lpr.gate")


class VivotekGate:
    def __init__(self, host, user, password, channel=0, open_ms=3000,
                 cooldown_sec=10, scheme="http"):
        self.base = f"{scheme}://{host}/cgi-bin/dido/setdo.cgi"
        self.user, self.password, self.ch = user, password, channel
        self.open_ms, self.cooldown = open_ms, cooldown_sec
        self._last = 0.0
        self._lock = threading.Lock()

    def _set(self, value):
        url = f"{self.base}?do{self.ch}={value}"
        r = requests.get(url, auth=HTTPDigestAuth(self.user, self.password), timeout=3)
        if r.status_code == 401:
            r = requests.get(url, auth=HTTPBasicAuth(self.user, self.password), timeout=3)
        r.raise_for_status()

    def _pulse(self):
        try:
            self._set(1)
            time.sleep(self.open_ms / 1000.0)
            self._set(0)
            log.info("เปิดประตูเรียบร้อย")
        except Exception as e:  # noqa: BLE001
            log.error("สั่งเปิดประตูไม่สำเร็จ: %s", e)

    def open_async(self):
        with self._lock:
            if time.time() - self._last < self.cooldown:
                return
            self._last = time.time()
        threading.Thread(target=self._pulse, daemon=True).start()

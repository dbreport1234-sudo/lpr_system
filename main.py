import argparse
import logging

import uvicorn

from lpr.api import create_app
from lpr.config import load_config
from lpr.manager import Manager
from lpr.ocr import ThaiPlateOCR
from lpr.storage import Storage


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    cfg = load_config(args.config)
    storage = Storage(cfg["storage"]["db_path"], cfg["storage"]["image_dir"])

    # ครั้งแรก: นำกล้องจาก camera.yaml เข้าฐานข้อมูล (หลังจากนั้นจัดการกล้องผ่านหน้าเว็บ)
    c = cfg["camera"]
    if not storage.cameras() and c["ip"] and c["password"]:
        storage.save_camera(dict(name="กล้อง 1", ip=c["ip"], username=c["username"], password=c["password"],
                                 rtsp_port=c["rtsp_port"], http_port=c["http_port"], stream_path=c["stream_path"],
                                 url_encode=int(c["url_encode_password"]), direction="both",
                                 enabled=1, gate_enabled=int(bool(cfg["gate"].get("enabled"))),
                                 do_channel=cfg["gate"].get("do_channel", 0)))
    mgr = Manager(cfg, storage, ThaiPlateOCR(gpu=cfg["ocr"]["gpu"], min_conf=cfg["ocr"]["min_conf"]))
    mgr.start_all()
    api = cfg["api"]
    uvicorn.run(create_app(storage, mgr), host=api["host"], port=api["port"], log_level="info")


if __name__ == "__main__":
    main()

"""ดาวน์โหลดโมเดลตรวจจับป้ายทะเบียน (YOLOv8n) มาไว้ที่ models/plate.pt

แหล่งโมเดล (license MIT ทั้งคู่):
  1) GitHub Muhammad-Zeerak-Khan/Automatic-License-Plate-Recognition-using-YOLOv8 (license_plate_detector.pt)
  2) Hugging Face Koushim/yolov8-license-plate-detection (สำรอง)
  - ฝึกกับป้ายหลายประเทศ ไม่ได้เจาะจงป้ายไทย ต้องทดสอบกับภาพกล้องจริง
  - ใช้โมเดลอื่นได้:  python download_model.py --url <ลิงก์ .pt>  หรือวางไฟล์เองที่ models/plate.pt
"""
import argparse
import os
import shutil
import sys
import urllib.request

SOURCES = [
    "https://github.com/Muhammad-Zeerak-Khan/Automatic-License-Plate-Recognition-using-YOLOv8/raw/main/license_plate_detector.pt",
    "https://huggingface.co/Koushim/yolov8-license-plate-detection/resolve/main/best.pt",
]
KNOWN_SHA256 = "8ec3b254a6c87610f037a90957462cafa11a9c03224e33a28c6a1d1ac2ac51b0"
DEST = os.path.join("models", "plate.pt")


def download(url, dest_tmp):
    req = urllib.request.Request(url, headers={"User-Agent": "lpr-installer"})
    with urllib.request.urlopen(req, timeout=60) as r, open(dest_tmp, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        done = 0
        while True:
            chunk = r.read(1 << 16)
            if not chunk:
                break
            f.write(chunk)
            done += len(chunk)
            if total:
                print(f"\r  ดาวน์โหลด {done/1e6:.1f}/{total/1e6:.1f} MB", end="", flush=True)
    print()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", help="ลิงก์โมเดลอื่น (.pt) แทนแหล่งเริ่มต้น")
    ap.add_argument("--force", action="store_true", help="ดาวน์โหลดทับไฟล์เดิม")
    a = ap.parse_args()

    if os.path.isfile(DEST) and not a.force:
        print(f"[ OK ] มี {DEST} อยู่แล้ว (ใช้ --force เพื่อดาวน์โหลดใหม่)")
        return 0
    os.makedirs("models", exist_ok=True)
    tmp = DEST + ".part"
    ok = False
    for url in ([a.url] if a.url else SOURCES):
        print(f"[....] ดาวน์โหลดโมเดลจาก {url}")
        try:
            download(url, tmp)
            if os.path.getsize(tmp) < 1_000_000:
                print("[WARN] ไฟล์เล็กผิดปกติ (อาจเป็นหน้าเว็บ) ลองแหล่งถัดไป")
                continue
            ok = True
            break
        except Exception as e:  # noqa: BLE001
            print(f"[WARN] ดาวน์โหลดไม่สำเร็จ: {e}")
    if not ok:
        print("[FAIL] ดาวน์โหลดโมเดลไม่ได้ ให้โหลดไฟล์ .pt ด้วยเบราว์เซอร์แล้วเปลี่ยนชื่อเป็น models\\plate.pt")
        if os.path.exists(tmp):
            os.remove(tmp)
        return 1
    import hashlib
    h = hashlib.sha256(open(tmp, "rb").read()).hexdigest()
    if not a.url and h != KNOWN_SHA256:
        print(f"[WARN] sha256 ไม่ตรงกับที่ตรวจสอบไว้ ({h[:12]}...) แหล่งอาจอัปเดตไฟล์")
    try:
        from ultralytics import YOLO
        names = YOLO(tmp).names
        print(f"[ OK ] โหลดโมเดลได้ classes = {names}")
    except Exception as e:  # noqa: BLE001
        print(f"[FAIL] ไฟล์โมเดลใช้งานไม่ได้: {e}")
        os.remove(tmp)
        return 1
    shutil.move(tmp, DEST)
    print(f"[ OK ] บันทึกที่ {DEST}")
    if len(names) > 1:
        print("[WARN] โมเดลมีหลาย class ให้ตั้ง detector.classes ใน config.yaml เป็น class ของป้ายทะเบียน")
    return 0


if __name__ == "__main__":
    sys.exit(main())

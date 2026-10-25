"""ตรวจความพร้อมของระบบ LPR  (python check_env.py)"""
import importlib
import os
import re
import socket
import sys
import threading

os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp|stimeout;5000000")
OK, WARN, FAIL = "[ OK ]", "[WARN]", "[FAIL]"
fails = warns = 0


_TH_NORMAL = "_ๅ/-ภถุึคตจขช" "ๆไำพะัีรนยบลฃ" "ฟหกดเ้่าสวง" "ผปแอิืทมใฝ"
_EN_NORMAL = "`1234567890-=" "qwertyuiop[]\\" "asdfghjkl;'" "zxcvbnm,./"
_TH_SHIFT = "%+๑๒๓๔ู฿๕๖๗๘๙" "๐\"ฎฑธํ๊ณฯญฐ,ฅ" "ฤฆฏโฌ็๋ษศซ." "()ฉฮฺ์?ฒฬฦ"
_EN_SHIFT = "~!@#$%^&*()_+" "QWERTYUIOP{}|" "ASDFGHJKL:\"" "ZXCVBNM<>?"
TH2EN = dict(zip(_TH_NORMAL, _EN_NORMAL))
TH2EN.update(dict(zip(_TH_SHIFT, _EN_SHIFT)))


def thai_to_latin(text):
    return "".join(TH2EN.get(c, c) for c in text)


non_ascii = False


def say(tag, msg):
    global fails, warns
    fails += tag == FAIL
    warns += tag == WARN
    print(f"{tag} {msg}")


def grab_frame(u, timeout=15):
    import cv2
    res = {}

    def run():
        cap = cv2.VideoCapture(u, cv2.CAP_FFMPEG)
        ok, fr = cap.read() if cap.isOpened() else (False, None)
        res["frame"] = fr if ok else None
        cap.release()

    th = threading.Thread(target=run, daemon=True)
    th.start()
    th.join(timeout)
    return res.get("frame")


v = sys.version_info
if v < (3, 9):
    say(FAIL, f"Python {v.major}.{v.minor} เก่าเกินไป (ต้อง 3.9+)")
elif v >= (3, 13):
    say(WARN, f"Python {v.major}.{v.minor}: แนะนำ 3.10–3.12")
else:
    say(OK, f"Python {v.major}.{v.minor}")

for mod in ["cv2", "numpy", "yaml", "ultralytics", "easyocr", "fastapi", "uvicorn", "requests"]:
    try:
        importlib.import_module(mod)
        say(OK, f"import {mod}")
    except Exception as e:  # noqa: BLE001
        say(FAIL, f"import {mod} ไม่ได้: {e}")

try:
    import torch
    if torch.cuda.is_available():
        say(OK, f"GPU: {torch.cuda.get_device_name(0)}")
    else:
        say(WARN, "ไม่พบ CUDA GPU จะรันด้วย CPU (ช้ากว่า)")
except Exception:  # noqa: BLE001
    pass

cfg = None
try:
    from lpr.config import load_config
    cfg = load_config("config.yaml")
    say(OK, "อ่าน config.yaml ได้")
except Exception as e:  # noqa: BLE001
    say(FAIL, f"อ่าน config.yaml ไม่ได้: {e}")

if cfg:
    cam = cfg["camera"]
    for e in cam.get("env_ignored", []):
        say(WARN, f"พบตัวแปรสภาพแวดล้อม {e} ในเครื่องที่ต่างจาก camera.yaml (ระบบใช้ค่าใน camera.yaml) ลบทิ้งได้: reg delete \"HKCU\\Environment\" /v {e} /f")
    # ---- camera.yaml ----
    if not os.path.isfile(cam["camera_file"]):
        say(FAIL, "ไม่พบไฟล์ camera.yaml")
    elif not cam["ip"] or not cam["username"]:
        say(FAIL, "camera.yaml: ยังไม่ได้กรอก ip / username")
    elif not cam["password"]:
        say(FAIL, "camera.yaml: ยังไม่ได้กรอก password  (เปิดไฟล์ camera.yaml แล้วใส่รหัสผ่านกล้อง)")
    else:
        say(OK, f"camera.yaml: {cam['username']}@{cam['ip']}")
        pw = cam["password"]
        mask = f"{len(pw)} ตัวอักษร ขึ้นต้น '{pw[0]}' ลงท้าย '{pw[-1]}'"
        print(f"[INFO] password ที่อ่านได้จาก camera.yaml: {mask}  (เทียบกับรหัสจริงของคุณ)")
        if cam.get("password_type") != "str":
            say(WARN, f"YAML อ่าน password เป็นชนิด {cam['password_type']} (ไม่ใช่ข้อความ) ให้ใส่เครื่องหมายคำพูดครอบ เช่น password: \"0123456\"")
        if any(ord(c) > 127 for c in cam["username"] + pw):
            non_ascii = True
            say(FAIL, "username/password ใน camera.yaml มีอักษรที่ไม่ใช่ภาษาอังกฤษ (เช่นอักษรไทย) รหัสกล้องปกติเป็นภาษาอังกฤษ/ตัวเลข")
            print("       - น่าจะพิมพ์ตอนเปิดคีย์บอร์ดไทย: สลับเป็นภาษาอังกฤษ (กด Win+Space หรือ Alt+Shift หรือปุ่ม ` ) แล้วพิมพ์ใหม่")
            print(f"       - ถ้าตั้งใจพิมพ์ตอนคีย์บอร์ดไทยเปิดอยู่ ค่าที่ตั้งใจพิมพ์คือ: username='{thai_to_latin(cam['username'])}' password='{thai_to_latin(pw)}'")
            print("       - ข้ามการทดสอบเชื่อมต่อกล้อง เพื่อไม่ให้ล็อกอินผิดซ้ำจนบัญชีถูกล็อก")
        if pw != pw.strip():
            say(WARN, "password มีช่องว่างหน้า/หลัง")

    # ---- โมเดล ----
    w = cfg["detector"]["weights"]
    if os.path.isfile(w):
        try:
            from ultralytics import YOLO
            names = YOLO(w).names
            say(OK, f"โมเดล {w} ใช้งานได้ classes={names}")
            if len(names) > 1 and not cfg["detector"].get("classes"):
                say(WARN, "โมเดลมีหลาย class ให้ตั้ง detector.classes ใน config.yaml")
        except Exception as e:  # noqa: BLE001
            say(FAIL, f"โหลดโมเดล {w} ไม่ได้: {e}")
    else:
        say(FAIL, f"ไม่พบโมเดล {w}  (รัน: python download_model.py)")

    # ---- ที่เก็บภาพ ----
    try:
        os.makedirs(cfg["storage"]["image_dir"], exist_ok=True)
        t = os.path.join(cfg["storage"]["image_dir"], ".w")
        open(t, "w").close(); os.remove(t)
        say(OK, "เขียนโฟลเดอร์เก็บภาพได้")
    except Exception as e:  # noqa: BLE001
        say(FAIL, f"เขียนโฟลเดอร์เก็บภาพไม่ได้: {e}")

    # ---- กล้อง ----
    if cam["ip"]:
        try:
            socket.create_connection((cam["ip"], cam["rtsp_port"]), timeout=4).close()
            say(OK, f"เชื่อมต่อ {cam['ip']}:{cam['rtsp_port']} ได้")
            reachable = True
        except Exception as e:  # noqa: BLE001
            say(FAIL, f"เชื่อมต่อกล้อง {cam['ip']}:{cam['rtsp_port']} ไม่ได้: {e}")
            reachable = False
        http_ok = None
        if reachable and cam["password"] and not non_ascii:
            # ทดสอบล็อกอินผ่านเว็บของกล้องก่อน เพื่อแยกว่า "รหัสผิด" หรือ "ปัญหา RTSP" (ลดจำนวนครั้งที่ลองผิด)
            try:
                import requests
                from requests.auth import HTTPBasicAuth, HTTPDigestAuth
                u = f"http://{cam['ip']}:{cam['http_port']}/cgi-bin/admin/getparam.cgi?system_info_modelname"
                r = requests.get(u, auth=HTTPDigestAuth(cam["username"], cam["password"]), timeout=5)
                if r.status_code == 401:
                    r = requests.get(u, auth=HTTPBasicAuth(cam["username"], cam["password"]), timeout=5)
                if r.status_code == 200:
                    http_ok = True
                    say(OK, f"ล็อกอินหน้าเว็บกล้องสำเร็จ ({r.text.strip()[:60]})")
                elif r.status_code == 401:
                    http_ok = False
                    say(FAIL, "กล้องปฏิเสธ username/password (HTTP 401) แก้ camera.yaml ให้ตรงกับที่ล็อกอินหน้าเว็บกล้องได้")
                else:
                    say(WARN, f"ทดสอบล็อกอินผ่าน HTTP ได้สถานะ {r.status_code} (ข้ามไปทดสอบ RTSP)")
            except Exception as e:  # noqa: BLE001
                say(WARN, f"ทดสอบล็อกอินผ่าน HTTP ไม่ได้: {e}")
        if reachable and cam["password"] and not non_ascii and http_ok is not False:
            frame = grab_frame(cam["rtsp_url"])
            if frame is None:
                print("[INFO] ลองใหม่โดยสลับรูปแบบการเข้ารหัสรหัสผ่านใน URL")
                frame = grab_frame(cam["rtsp_url_alt"])
                if frame is not None:
                    new = "false" if cam["url_encode_password"] else "true"
                    txt = open(cam["camera_file"], encoding="utf-8").read()
                    txt = re.sub(r"(?m)^url_encode_password:\s*\w+", f"url_encode_password: {new}", txt)
                    open(cam["camera_file"], "w", encoding="utf-8").write(txt)
                    say(OK, f"สลับ url_encode_password เป็น {new} ใน camera.yaml แล้ว")
            if frame is not None:
                h, wd = frame.shape[:2]
                say(OK, f"ดึงภาพจากกล้องได้ {wd}x{h}")
                if wd < 1280:
                    say(WARN, "ความละเอียดต่ำ ป้ายอาจเล็กเกินไป ใช้ stream_path: /live1s1.sdp และตั้ง Stream 1 ให้ละเอียดสูง")
            else:
                say(FAIL, "ดึงภาพ RTSP ไม่ได้")
                if http_ok:
                    print("       - รหัสผ่านถูก (ล็อกอินเว็บได้) แต่ RTSP ปฏิเสธ: ตรวจในหน้าเว็บกล้องว่าเปิด RTSP authentication/สิทธิ์ผู้ใช้")
                print("       - 401 = username/password ไม่ตรง | 404 = stream_path ไม่ถูก ลอง /live1s2.sdp")
                print("       - อย่าลองผิดซ้ำหลายครั้ง Vivotek อาจล็อกบัญชีชั่วคราว")

print()
print(f"สรุป: FAIL={fails} WARN={warns}")
sys.exit(1 if fails else 0)

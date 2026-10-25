import os
from urllib.parse import quote

import yaml


def _expand(obj):
    if isinstance(obj, dict):
        return {k: _expand(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_expand(v) for v in obj]
    if isinstance(obj, str):
        return os.path.expandvars(obj)
    return obj


def _read_yaml(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def build_rtsp_url(user, password, ip, port, path, encode=True):
    path = path if path.startswith("/") else "/" + path
    q = (lambda s: quote(s, safe="")) if encode else (lambda s: s)
    cred = f"{q(user)}:{q(password)}@" if user else ""
    return f"rtsp://{cred}{ip}:{port}{path}"


def load_config(path: str = "config.yaml", camera_path: str = None) -> dict:
    cfg = _expand(_read_yaml(path))
    base = os.path.dirname(os.path.abspath(path))
    cam_file = camera_path or cfg.get("camera_file", "camera.yaml")
    if not os.path.isabs(cam_file):
        cam_file = os.path.join(base, cam_file)
    cam = _read_yaml(cam_file) if os.path.isfile(cam_file) else {}

    # ไฟล์ camera.yaml มาก่อนเสมอ ตัวแปรสภาพแวดล้อม (CAM_IP/CAM_USER/CAM_PASS) ใช้เฉพาะเมื่อช่องนั้นในไฟล์ว่าง
    # (สะดวกตอนใช้ Docker) ค่าที่ตกค้างในเครื่องจะไม่ทับค่าในไฟล์อีกต่อไป
    env_ignored = []
    for key, env in (("ip", "CAM_IP"), ("username", "CAM_USER"), ("password", "CAM_PASS")):
        ev = os.environ.get(env)
        if not ev:
            continue
        if cam.get(key):
            if str(cam[key]) != ev:
                env_ignored.append(env)
        else:
            cam[key] = ev

    pw_type = type(cam.get("password")).__name__  # str ถ้าถูกต้อง; int/bool/NoneType = YAML แปลงค่าให้เอง
    ip = str(cam.get("ip") or "")
    user = str(cam.get("username") or "")
    pw = str(cam.get("password") or "")
    port = int(cam.get("rtsp_port") or 554)
    http_port = int(cam.get("http_port") or 80)
    spath = str(cam.get("stream_path") or "/live1s1.sdp")
    enc = bool(cam.get("url_encode_password", True))

    c = cfg.setdefault("camera", {})
    c.update(
        ip=ip, username=user, password=pw, rtsp_port=port, http_port=http_port,
        stream_path=spath, url_encode_password=enc, camera_file=cam_file, password_type=pw_type, env_ignored=env_ignored,
        rtsp_url=build_rtsp_url(user, pw, ip, port, spath, enc),
        rtsp_url_alt=build_rtsp_url(user, pw, ip, port, spath, not enc),
    )
    g = cfg.setdefault("gate", {})
    g["host"] = ip if http_port == 80 else f"{ip}:{http_port}"
    g["user"], g["password"] = user, pw
    return cfg

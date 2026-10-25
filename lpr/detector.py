"""ตรวจจับป้ายทะเบียนด้วย YOLO + ByteTrack (ในตัว ultralytics)"""
from dataclasses import dataclass


@dataclass
class Detection:
    track_id: int
    box: tuple  # x1,y1,x2,y2 (int)
    conf: float


class PlateDetector:
    def __init__(self, weights, conf=0.4, imgsz=960, device="cpu", tracker="bytetrack.yaml", classes=None):
        from ultralytics import YOLO

        self.model = YOLO(weights)
        self.conf, self.imgsz, self.device, self.tracker = conf, imgsz, device, tracker
        self.classes = classes

    def track(self, frame):
        res = self.model.track(
            frame,
            persist=True,
            conf=self.conf,
            imgsz=self.imgsz,
            device=self.device,
            tracker=self.tracker,
            classes=self.classes,
            verbose=False,
        )[0]
        out = []
        boxes = res.boxes
        if boxes is None or len(boxes) == 0 or boxes.id is None:
            return out
        xyxy = boxes.xyxy.cpu().numpy()
        confs = boxes.conf.cpu().numpy()
        ids = boxes.id.int().cpu().tolist()
        for b, c, i in zip(xyxy, confs, ids):
            out.append(Detection(i, tuple(int(v) for v in b), float(c)))
        return out

"""OCR ป้ายไทย (EasyOCR th+en) พร้อม preprocess และจัดกลุ่มบรรทัด"""
import cv2
import numpy as np

from .thai_plate import parse_lines


class ThaiPlateOCR:
    def __init__(self, gpu=False, min_conf=0.3):
        import easyocr

        self.reader = easyocr.Reader(["th", "en"], gpu=gpu, verbose=False)
        self.min_conf = min_conf

    @staticmethod
    def preprocess(crop):
        h = crop.shape[0]
        scale = min(4.0, max(1.0, 160.0 / max(h, 1)))
        if scale > 1.0:
            crop = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        gray = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4)).apply(gray)
        return gray

    @staticmethod
    def _group_lines(results):
        items = []
        for bbox, text, conf in results:
            ys = [p[1] for p in bbox]
            xs = [p[0] for p in bbox]
            items.append({"yc": float(np.mean(ys)), "h": max(ys) - min(ys),
                          "x": min(xs), "text": text, "conf": conf})
        if not items:
            return [], 0.0
        items.sort(key=lambda d: d["yc"])
        med_h = float(np.median([d["h"] for d in items])) or 1.0
        lines, cur = [], [items[0]]
        for it in items[1:]:
            if it["yc"] - cur[-1]["yc"] > 0.6 * med_h:
                lines.append(cur)
                cur = [it]
            else:
                cur.append(it)
        lines.append(cur)
        texts = [" ".join(d["text"] for d in sorted(l, key=lambda d: d["x"])) for l in lines]
        conf = float(np.mean([d["conf"] for d in items]))
        return texts, conf

    def read(self, crop):
        """คืน (plate, province, conf) หรือ None"""
        img = self.preprocess(crop)
        results = [r for r in self.reader.readtext(img, detail=1, paragraph=False)
                   if r[2] >= self.min_conf * 0.5]
        lines, conf = self._group_lines(results)
        if not lines:
            return None
        plate, province = parse_lines(lines)
        if not plate or conf < self.min_conf:
            return None
        return plate, province, conf

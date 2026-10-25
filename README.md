# ระบบ LPR ป้ายทะเบียนไทย + Vivotek IB9387-EHTV-V3

```
กล้อง (RTSP) → RTSPCamera (เฟรมล่าสุด, reconnect)
             → YOLO + ByteTrack (ตรวจป้าย + ติดตาม ID)
             → OCR (EasyOCR th+en) เฉพาะเฟรมที่ป้ายใหญ่พอ
             → Voting ต่อ track (เลือกผลที่อ่านตรงกันหลายเฟรม)
             → SQLite + รูปหลักฐาน + Whitelist
             → สั่ง DO กล้องเปิดไม้กั้น (ถ้าเปิดใช้) → REST API + Dashboard
```

## ติดตั้ง
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# 1) กรอก IP / username / password กล้องในไฟล์ camera.yaml
# 2) โมเดลตรวจจับป้ายมีให้แล้วที่ models/plate.pt (ดู models/README.txt) โหลดใหม่: python download_model.py --force
python check_env.py             # ตรวจความพร้อม
python main.py            # เปิด http://localhost:8000
python main.py --source test.mp4   # ทดสอบด้วยวิดีโอ
pytest tests              # ทดสอบกฎป้ายไทย
```

## สิ่งที่ต้องเตรียมเอง
1. **โมเดลตรวจจับป้าย `models/plate.pt`** (YOLOv8/11, class เดียว = plate)
   เทรนจาก dataset ป้ายไทย (เช่นบน Roboflow Universe) ด้วยภาพจากกล้องจริงของคุณจะแม่นที่สุด
   `yolo train model=yolo11n.pt data=plate.yaml imgsz=960 epochs=100`
2. ตรวจ **URL สั่ง Digital Output** (`/cgi-bin/dido/setdo.cgi`) กับเอกสาร Vivotek URL Command
   ของเฟิร์มแวร์ที่ใช้อยู่ และตั้ง DO ในหน้าเว็บกล้องให้ตรงกับรีเลย์

## ตั้งค่ากล้อง (สำคัญที่สุดต่อความแม่นยำ)
- Stream 1: H.264, ความละเอียดเต็ม/2MP, 15–25 fps, bitrate สูงพอ (CBR 6–8 Mbps), I-frame 1 วินาที
- **Shutter สูงสุด 1/1000s ขึ้นไป** (รถวิ่ง) ลด Gain, ปิด/ลด WDR และ DNR แรง ๆ ที่ทำให้ภาพเบลอ
- Day/Night + IR: ป้ายสะท้อนแสงอาจ "ขาวโพลน" กลางคืน ให้ลอง exposure ต่ำลง / ปรับกำลัง IR
- ใช้ Motorized lens ซูมให้ **ป้ายกว้าง ≥ 120–150 px** ที่จุดอ่าน
- มุมกล้อง: แนวนอน ≤ ~25–30°, แนวตั้ง ≤ ~15° และตั้งโฟกัสที่ระยะจุดอ่านจริง

## จูนระบบ
| ปัญหา | ปรับ |
|---|---|
| อ่านผิดบ่อย | เพิ่ม `confirm_votes`, `min_conf`, `min_plate_width_px` |
| ช้า/CPU เต็ม | เพิ่ม `ocr_every_n_frames`, ใช้ GPU (`device: "0"`, `ocr.gpu: true`) |
| ตรวจเจอป้ายนอกเลน | กำหนด `roi` |
| บันทึกซ้ำ | เพิ่ม `dedupe_sec` |

## API
`GET /events?limit=&plate=` · `GET /events/{id}` · `GET /events/{id}/image?kind=full|plate` · `GET /health`

> ความปลอดภัย: API ไม่มี authentication ให้วางหลัง reverse proxy/VPN และเก็บข้อมูลตาม PDPA

## หน้าเว็บ (เวอร์ชันหลายกล้อง)
เปิด `http://localhost:8000` : ภาพสด · เหตุการณ์ (ค้นหา/ส่งออก CSV) · รายงาน (พิมพ์/PDF) · จัดการกล้อง · Whitelist/Blacklist
- ครั้งแรกระบบนำกล้องจาก `camera.yaml` เข้าฐานข้อมูลให้ หลังจากนั้นเพิ่ม/แก้/ลบกล้องในหน้าเว็บ (รหัสผ่านไม่ถูกส่งกลับมาแสดง)
- 1 กล้อง = 1 เธรด + โมเดล/ตัวติดตามของตัวเอง ส่วน OCR ใช้ร่วมกัน ถ้าใช้ CPU หลายกล้องจะช้าลงตามจำนวน
- รองรับกล้อง Vivotek, Dahua (`/cam/realmonitor?channel=N&subtype=0|1`) และ RTSP ทั่วไป (กำหนด path เอง) สั่งเปิดประตูผ่าน DO รองรับเฉพาะ Vivotek
- ยังไม่มี: ระบบล็อกอิน/สิทธิ์ผู้ใช้ (วางหลัง VPN/reverse proxy), แก้ไขทะเบียนที่อ่านผิด, แจ้งเตือน Blacklist, รายงาน Excel, ตั้ง ROI ในหน้าเว็บ, ลบข้อมูลเก่าอัตโนมัติ

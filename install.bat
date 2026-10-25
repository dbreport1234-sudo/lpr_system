@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ==========================================
echo   LPR: ตรวจความพร้อม + ติดตั้ง
echo ==========================================

where python >nul 2>&1
if errorlevel 1 (
  echo [FAIL] ไม่พบ Python  ติดตั้ง Python 3.10-3.12 จาก python.org
  echo        และติ๊ก "Add python.exe to PATH" ตอนติดตั้ง
  pause & exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo [....] สร้าง virtual environment
  python -m venv .venv
  if errorlevel 1 ( echo [FAIL] สร้าง venv ไม่สำเร็จ & pause & exit /b 1 )
)
call ".venv\Scripts\activate.bat"

echo [....] อัปเดต pip
python -m pip install --upgrade pip >nul

where nvidia-smi >nul 2>&1
if errorlevel 1 (
  echo [INFO] ไม่พบ NVIDIA GPU จะติดตั้งแบบ CPU
) else (
  echo [INFO] พบ NVIDIA GPU  หากต้องการใช้ GPU ให้ติดตั้ง torch CUDA ตามคำสั่งที่ pytorch.org ก่อนรันสคริปต์นี้
)

echo [....] ติดตั้งไลบรารี (ครั้งแรกอาจใช้เวลาหลายนาที)
pip install -r requirements.txt
if errorlevel 1 ( echo [FAIL] ติดตั้งไลบรารีไม่สำเร็จ & pause & exit /b 1 )

echo.
if not exist "models\plate.pt" (
  echo [....] ดาวน์โหลดโมเดลตรวจจับป้ายทะเบียน
  python download_model.py
)
echo.
echo ===== ตรวจสอบระบบ =====
python check_env.py
set RC=%errorlevel%
echo.
if %RC%==0 (
  echo พร้อมใช้งาน  รันด้วย run.bat
) else (
  echo ยังมีรายการ FAIL ด้านบน (เช่น กรอกรหัสผ่านใน camera.yaml) แล้วรัน check.bat เพื่อตรวจซ้ำ
)
pause
exit /b %RC%

@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\activate.bat" ( echo ยังไม่ได้ติดตั้ง รัน install.bat ก่อน & pause & exit /b 1 )
call ".venv\Scripts\activate.bat"
python check_env.py >nul 2>&1
if errorlevel 1 (
  echo ตรวจระบบไม่ผ่าน กำลังแสดงรายละเอียด...
  python check_env.py
  pause & exit /b 1
)
echo เริ่มระบบ LPR  เปิด http://localhost:8000
python main.py %*
pause

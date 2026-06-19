@echo off
chcp 65001 >nul
echo ============================================
echo   VietSTT Web App - http://localhost:5000
echo ============================================
echo.

echo [1] Kiem tra va cai thu vien...
py -3.13 -c "import flask" 2>nul || py -3.13 -m pip install flask
py -3.13 -c "import docx" 2>nul  || py -3.13 -m pip install python-docx

echo [2] Khoi dong server...
echo.
echo    Mo trinh duyet: http://localhost:5000
echo    Nhan Ctrl+C de dung server
echo.

cd /d "%~dp0"
py -3.13 app.py

pause

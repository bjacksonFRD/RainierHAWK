@echo off
setlocal

cd /d "C:\Users\Brent Jackson\Desktop\Frontier\Ranier\HAWK - Rainier"

:: Crexi
python universal_ocr_automation.py "https://www.crexi.com"

:: Dropbox
python universal_ocr_automation.py "https://www.dropbox.com/login"

:: Box
python universal_ocr_automation.py "https://account.box.com/login"

:: 10x
python universal_ocr_automation.py "https://www.10x.com"

:: CoStar
python universal_ocr_automation.py "https://www.costar.com"

endlocal
pause

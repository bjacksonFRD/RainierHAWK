@echo off
setlocal

cd /d "%~dp0"

echo [07:10 PM CDT] STEP 0: Login to Crexi...
python -u login_to_crexi.py
if %ERRORLEVEL% NEQ 0 echo [07:10 PM CDT] ERROR: Login failed & goto :end

echo [07:10 PM CDT] STEP 1: Email intake...
python -u email_intake_graph_router.py
if %ERRORLEVEL% NEQ 0 echo [07:10 PM CDT] ERROR: Email intake failed & goto :end

echo [07:10 PM CDT] Intake log (tail):
powershell -NoP -C "(Get-Content '.\Logs\email_intake.log' -Tail 8 -ErrorAction SilentlyContinue)"

echo [07:10 PM CDT] Queue size (gated links):
if exist ".\Logs\gated_queue.json" (powershell -NoP -C "(gc '.\Logs\gated_queue.json'|Select-String '\"url\"').Count" ) else (echo 0 )

echo [07:10 PM CDT] STEP 1.5: Prune queue...
python -u queue_prune.py
if %ERRORLEVEL% NEQ 0 echo [07:10 PM CDT] ERROR: Queue pruning failed & goto :end

echo [07:10 PM CDT] STEP 2: Playwright click-through...
python -u broker_clicker_playwright.py
if %ERRORLEVEL% NEQ 0 echo [07:10 PM CDT] ERROR: Clicker failed & goto :end

echo [07:10 PM CDT] STEP 3: Agent (normalize/summary/label)...
python -u om_agent.py 1>>".\Logs\agent.log" 2>&1
if %ERRORLEVEL% NEQ 0 echo [07:10 PM CDT] ERROR: Agent failed & goto :end

echo [07:10 PM CDT] Agent log (tail):
powershell -NoP -C "(Get-Content '.\Logs\agent.log' -Tail 8 -ErrorAction SilentlyContinue)"

echo [07:10 PM CDT] Summary:
powershell -NoP -C "if (Test-Path '.\Outputs\labels_log.csv') {(Import-Csv '.\Outputs\labels_log.csv'|Group-Object label|Select-Object Name,Count|Format-Table -AutoSize|Out-String).Trim()} else {Write-Output 'No labels_log.csv found'}"

echo [07:10 PM CDT] Done.

:end
endlocal
pause
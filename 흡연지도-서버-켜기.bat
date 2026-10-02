@echo off
chcp 65001 >nul
title 서울 흡연구역 지도 (8752)
cd /d "C:\Users\lapla\smoking-map"
REM 이미 떠 있는 8752 서버를 먼저 정리한다
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name like '%%python%%'\" | Where-Object { $_.CommandLine -like '*http.server*8752*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
start "" http://localhost:8752/
"C:\Users\lapla\smoking-map\.venv\Scripts\python.exe" -m http.server 8752 --bind 127.0.0.1 --directory "C:\Users\lapla\smoking-map\web"

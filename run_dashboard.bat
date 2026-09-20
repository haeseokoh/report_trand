@echo off
chcp 65001 > nul
title 리포트 트렌드 인텔리전스 실행기

echo ========================================================
echo  📈 주식/산업 리포트 트렌드 인텔리전스 시스템을 시작합니다...
echo ========================================================

cd /d "c:\project\angravity\report_trand"

:: 2초 후 브라우저 자동 오픈
start "" "http://localhost:8000"

:: 서버 실행
python main.py --server-only --port 8000

pause

@echo off
title OneContext Backend (FastAPI :8000)
cd /d "C:\Users\Suresh\Desktop\one_mem\onecontext"
echo ========================================================
echo   Starting OneContext FastAPI Backend on Port 8000...
echo ========================================================
"C:\Users\Suresh\AppData\Local\Programs\Python\Python313\Scripts\uvicorn.exe" backend.main:app --reload --port 8000
pause

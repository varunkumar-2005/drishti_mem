@echo off
cd /d "%~dp0"
echo Starting OneContext Backend and Frontend...
start "OneContext Backend" run_backend.bat
start "OneContext Frontend" run_frontend.bat
echo Both servers launched in separate windows!
echo Open http://localhost:5173 in your browser once Vite shows ready.

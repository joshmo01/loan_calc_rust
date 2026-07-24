@echo off
cd /d "%~dp0"
if exist .env (
  for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
    if not "%%A"=="" if not "%%A:~0,1%"=="#" set "%%A=%%B"
  )
)
if "%CEREBRAS_API_KEY%"=="" (
  echo Set CEREBRAS_API_KEY first:
  echo   set CEREBRAS_API_KEY=csk-...
  echo Or create .env from .env.example
  pause
  exit /b 1
)
if "%LLM_BASE_URL%"=="" set LLM_BASE_URL=https://api.cerebras.ai/v1
if "%LLM_MODEL%"=="" set LLM_MODEL=gemma-4-31b
if "%PORT%"=="" set PORT=8790
echo Open http://localhost:%PORT%/
python chat\server.py
pause

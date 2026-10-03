@echo off
setlocal

set "ROOT_DIR=%~dp0"

where uv >nul 2>nul
if errorlevel 1 (
    echo uv nao encontrado. Instale em https://docs.astral.sh/uv/ e tente novamente.
    echo.
    pause
    exit /b 1
)

pushd "%ROOT_DIR%" >nul
uv run keytune
set "EXIT_CODE=%ERRORLEVEL%"
popd >nul

if not "%EXIT_CODE%"=="0" (
    echo.
    echo O player terminou com codigo %EXIT_CODE%.
    pause
)

exit /b %EXIT_CODE%

@echo off
setlocal

set "ROOT_DIR=%~dp0"
set "VENV_PYTHON=%ROOT_DIR%.venv\Scripts\python.exe"
set "PLAYER_ENTRY=%ROOT_DIR%src\main.py"

if not exist "%VENV_PYTHON%" (
    echo Ambiente virtual nao encontrado em "%ROOT_DIR%.venv".
    echo.
    echo Crie o ambiente e instale as dependencias com:
    echo   uv sync
    echo.
    pause
    exit /b 1
)

if not exist "%PLAYER_ENTRY%" (
    echo Arquivo de arranque nao encontrado: "%PLAYER_ENTRY%".
    echo Verifique se o script esta na raiz do projeto.
    echo.
    pause
    exit /b 1
)

pushd "%ROOT_DIR%" >nul
"%VENV_PYTHON%" "%PLAYER_ENTRY%"
set "EXIT_CODE=%ERRORLEVEL%"
popd >nul

if not "%EXIT_CODE%"=="0" (
    echo.
    echo O player terminou com codigo %EXIT_CODE%.
    pause
)

exit /b %EXIT_CODE%

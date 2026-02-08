@echo off

:: Check if already minimized
if "%minimized%"=="" (
    set minimized=true
    start /min cmd /C "%~dpnx0"
    exit /b
)

title Gestao Amicando Launcher
echo ==========================================
echo      Iniciando Gestao Amicando...
echo ==========================================
echo O prompt foi minimizado para nao atrapalhar.
echo Para fechar o programa, feche esta janela ou use Ctrl+C.
echo OBS: Fechar a aba do navegador NAO para o servidor.
echo ==========================================

:: Navigate to the script's directory (root of the project)
cd /d "%~dp0"

:: Check if Streamlit is available
streamlit --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ALERTA] Streamlit nao encontrado no PATH.
    echo Tentando instalar dependencias...
    pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo [ERRO] Falha ao instalar dependencias. Verifique sua instalacao Python.
        pause
        exit /b
    )
)

:: Run the application
echo Iniciando aplicacao...
streamlit run Dashboard.py

:: Window will close when streamlit stops
exit

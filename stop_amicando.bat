@echo off
echo ==========================================
echo        Parando Gestao Amicando...
echo ==========================================
echo.

:: Tenta fechar processos pythonw.exe
taskkill /F /IM pythonw.exe /T

if %errorlevel% equ 0 (
    echo.
    echo Servidor parado com sucesso!
) else (
    echo.
    echo Nenhum processo do servidor encontrado ou erro ao parar.
)

timeout /t 3 >nul

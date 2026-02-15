@echo off
cd /d "%~dp0"
title Amicando - Sistema de Gestao
echo Iniciando o Sistema Amicando...
echo Nao feche esta janela enquanto estiver usando o sistema.
streamlit run Dashboard.py
pause

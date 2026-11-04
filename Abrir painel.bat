@echo off
rem Abre o painel do Auto_PES21 com um clique duplo, sem deixar janela preta.
rem Para ter o atalho na Area de Trabalho: no painel, aba Configuracao,
rem "Criar atalho na Area de Trabalho" (ou: python criar_atalho.py).
cd /d "%~dp0"
rem O pacote baixado do GitHub traz o proprio Python na pasta python\.
if exist "%~dp0python\pythonw.exe" (
    start "" "%~dp0python\pythonw.exe" painel.py
    exit /b
)
where pythonw >nul 2>nul
if %errorlevel%==0 (
    start "" pythonw painel.py
) else (
    python painel.py
)

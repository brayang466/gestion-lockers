@echo off
REM Exporta la BD y hace commit (y opcionalmente push) para tener el repo actualizado.
REM Ejecutar desde la raíz del proyecto: scripts\sincronizar_repo.bat

cd /d "%~dp0.."

echo Exportando base de datos...
python scripts/exportar_bd.py
if errorlevel 1 (
    echo Error al exportar. Revisa MySQL y .env
    pause
    exit /b 1
)

echo.
echo Añadiendo cambios al repo...
git add -A
git status

set /p CONFIRMAR="¿Hacer commit? (S/N): "
if /i not "%CONFIRMAR%"=="S" exit /b 0

set /p MSG="Mensaje del commit (Enter = 'Actualización BD y proyecto'): "
if "%MSG%"=="" set MSG=Actualización BD y proyecto
git commit -m "%MSG%"

set /p PUSH="¿Subir a GitHub (git push)? (S/N): "
if /i "%PUSH%"=="S" git push

echo Listo.
pause

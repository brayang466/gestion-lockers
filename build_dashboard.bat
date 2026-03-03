@echo off
echo Instalando y construyendo el dashboard React...
echo.
cd /d "%~dp0frontend"

if not exist "package.json" (
    echo ERROR: No se encuentra la carpeta frontend o package.json.
    echo Asegurate de estar en la raiz del proyecto: gestor_lockers
    pause
    exit /b 1
)

echo Carpeta actual: %CD%
echo.
echo Ejecutando: npm install
call npm install
if errorlevel 1 (
    echo.
    echo ERROR en npm install. ¿Tienes Node.js instalado?
    echo Descargalo desde: https://nodejs.org
    pause
    exit /b 1
)

echo.
echo Ejecutando: npm run build
call npm run build
if errorlevel 1 (
    echo.
    echo ERROR en npm run build.
    pause
    exit /b 1
)

echo.
echo Listo. El dashboard esta en app\static\dashboard
echo Reinicia o inicia Flask (python run.py) y entra a /dashboard
pause

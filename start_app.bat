@echo off
echo ==============================================
echo Iniciando Modeling Tool (Version mas reciente)
echo ==============================================
echo.

:: 1. Copiar .env si no existe
if not exist .env (
    echo Creando archivo .env a partir de .env.example...
    copy .env.example .env > nul
)

:: 2. Actualizar desde Github
echo [1/4] Actualizando con la ultima version de Github...
git pull origin main

:: 3. Verificar/Iniciar Docker Desktop
echo [2/4] Verificando Docker...
tasklist /FI "IMAGENAME eq Docker Desktop.exe" 2>NUL | find /I /N "Docker Desktop.exe">NUL
if "%ERRORLEVEL%"=="1" (
    echo Docker Desktop no esta abierto. Iniciando...
    if exist "C:\Program Files\Docker\Docker\Docker Desktop.exe" (
        start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
        echo Esperando 20 segundos para que Docker inicie completamente...
        timeout /t 20 /nobreak > nul
    ) else (
        echo ATENCION: No se pudo encontrar Docker Desktop en la ruta habitual.
        echo Por favor, abre Docker manualmente y luego presiona una tecla.
        pause
    )
)

:: 4. Levantar los contenedores de Docker
echo [3/4] Construyendo e iniciando los contenedores...
docker-compose up -d --build

:: 5. Esperar a que el frontend este listo
echo [4/4] Esperando a que la aplicacion este lista en el puerto 3000...
echo (Esto puede tardar unos segundos)
:loop
curl -s http://localhost:3000 > nul
if %errorlevel% neq 0 (
    timeout /t 2 /nobreak > nul
    goto loop
)

:: 6. Abrir en Chrome
echo.
echo Abriendo aplicacion en Chrome...
start chrome http://localhost:3000

echo.
echo ==============================================
echo ¡Listo! La aplicacion se esta ejecutando en Docker.
echo Puedes cerrar esta ventana cuando quieras.
echo ==============================================
pause

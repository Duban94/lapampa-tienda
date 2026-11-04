@echo off
rem Se ejecuta UNA vez en un PC con Windows (con internet) para fabricar Instalar_LaPampa.exe
cd /d "%~dp0"
echo === 1/3 Preparando herramientas de Python ===
py -m pip install --upgrade flask openpyxl pyxlsb pyinstaller || goto :error
echo.
echo === 2/3 Creando LaPampa.exe (incluye el historial actual de lapampa.db) ===
set SEMILLA=
if exist lapampa.db set SEMILLA=--add-data "lapampa.db;."
py -m PyInstaller --noconfirm --clean --onefile --windowed --name LaPampa --icon icono.ico --hidden-import openpyxl --hidden-import pyxlsb --add-data "templates;templates" %SEMILLA% app.py || goto :error
echo.
echo === 3/3 Creando el instalador ===
set ISCC=
for %%P in ("%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" "%ProgramFiles%\Inno Setup 6\ISCC.exe") do if exist %%P set ISCC=%%~P
if not defined ISCC (
  echo Instalando Inno Setup, la herramienta que crea instaladores...
  winget install -e --id JRSoftware.InnoSetup --accept-package-agreements --accept-source-agreements
  for %%P in ("%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" "%ProgramFiles%\Inno Setup 6\ISCC.exe") do if exist %%P set ISCC=%%~P
)
if not defined ISCC (
  echo No se pudo instalar Inno Setup solo. Descargalo de https://jrsoftware.org/isdl.php , instalalo y vuelve a ejecutar este archivo.
  goto :error
)
"%ISCC%" instalador.iss || goto :error
echo.
echo ============================================================
echo LISTO. El instalador esta en:  Instalador\Instalar_LaPampa.exe
echo Copialo al PC de la tienda y dale doble clic: instala el
echo programa y deja el acceso directo "La Pampa" en el Escritorio.
echo ============================================================
pause
exit /b 0
:error
echo.
echo Algo fallo (mira el mensaje de arriba).
pause
exit /b 1

@echo off
REM Archivo para ejecutar el sistema de ventas en Windows 11

REM ACTUALIZA ESTA RUTA A TU VERSIÓN DE PYTHON SI USAS venv
REM set "VENV_DIR=venv"

REM Si usas entorno virtual, descomenta la siguiente línea:
REM call %VENV_DIR%\Scripts\activate

REM Ejecuta el sistema principal (debe estar main.py en la raíz)
python main.py

REM Mantiene la ventana abierta al terminar (útil si hay error)
pause
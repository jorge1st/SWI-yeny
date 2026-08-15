Cómo compilar el instalador (Inno Setup):

1) Instalar Inno Setup (https://jrsoftware.org/isinfo.php).
2) Copiar la carpeta dist\\main (generada por PyInstaller) dentro del directorio del proyecto SWI.
3) Abrir Inno Setup Compiler (ISCC) y cargar installer.iss, o ejecutar en consola:
   ISCC.exe "installer.iss"
4) El instalador pedirá: Nombre de la empresa, RIF y la ruta donde guardar los PDFs; creará un config.json en C:\\ProgramData\\SWI\\config.json con esos valores.

Nota: El instalador necesita privilegios de administrador para instalar en Program Files y escribir en ProgramData.

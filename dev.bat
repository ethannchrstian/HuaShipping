@echo off
rem Start the development server. Usage: just type  dev  in the project folder,
rem or double-click this file. Stop with Ctrl+C.
rem   dev css   -> instead watch + rebuild the stylesheet while editing templates
rem               (needs tools\tailwindcss.exe; download URL in DESIGN.md)
cd /d "%~dp0"
if "%1"=="css" (
  "tools\tailwindcss.exe" -i "voyages\static\voyages\src\app.tailwind.css" -o "voyages\static\voyages\app.css" --watch
) else (
  ".venv\Scripts\python.exe" manage.py runserver
)

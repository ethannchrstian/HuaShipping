@echo off
rem Start the development server. Usage: just type  dev  in the project folder,
rem or double-click this file. Stop with Ctrl+C.
cd /d "%~dp0"
".venv\Scripts\python.exe" manage.py runserver

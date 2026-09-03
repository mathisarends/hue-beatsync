@echo off
rem Double-clickable wrapper around scripts\serve.ps1.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0serve.ps1" %*

@ECHO OFF

@REM Makes a ALOV Sanity Checker.exe!
@REM Requires: Python 3.5, pip, ffmpeg. Cannot cross compile: can only be executed on the same OS it was compiled on

python.exe -m pip install pyinstaller --upgrade
RD /S /Q dist
pyinstaller alov_sanity_checker.py --name "ALOV Sanity Checker" --add-binary "ffprobe.exe;." --add-data "ME1_complete.json;." --add-data "ME2_complete.json;." --add-data "ME3_complete.json;." --add-data "folder_mappings.json;." -D --icon "ALOV_Checker_square.ico"
RD /S /Q __pycache__
RD /S /Q build
DEL /Q "ALOV Sanity Checker.spec"
CLS
ECHO [101;93mWARNING: ffmpeg license may not allow you to distribute builds that include ffmpeg.[0m
ECHO.
pause

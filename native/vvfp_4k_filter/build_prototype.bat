@echo off
rem Builds the 4K filter research prototype (32-bit, like the games): build_prototype.bat <output folder>
rem Nothing here ships; the tools only read a frame file and write images and numbers.
setlocal
if "%~1"=="" (
  echo usage: build_prototype.bat ^<output folder^>
  exit /b 2
)
set OUT=%~1
set SRC=%~dp0
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars32.bat" >nul || exit /b 3
if not exist "%OUT%" mkdir "%OUT%"
cl /nologo /O2 /W4 /wd4204 /D_CRT_SECURE_NO_WARNINGS "/Fo%OUT%\\" "/Fe%OUT%\vv4k_upscale.exe" ^
   "%SRC%vv4k_upscale.c" "%SRC%vv4k_filters.c" || exit /b 4
cl /nologo /O2 /W4 /wd4204 /D_CRT_SECURE_NO_WARNINGS "/Fo%OUT%\\" "/Fe%OUT%\vv4k_gpu_probe.exe" ^
   "%SRC%vv4k_gpu_probe.c" "%SRC%vv4k_filters.c" user32.lib gdi32.lib d3d9.lib || exit /b 5
exit /b 0

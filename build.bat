@echo off
echo ===================================================
echo   FLAC Rebuilder PyInstaller打包批处理工具
echo ===================================================
echo 正在创建打包环境并使用 PyInstaller 进行编译...

uv run --with pyinstaller --with mutagen --with soundfile --with numpy pyinstaller --onefile --console flac_rebuilder.py

if %ERRORLEVEL% equ 0 (
    echo.
    echo ===================================================
    echo [✔] 打包成功！
    echo 生成的可执行文件位于: dist\flac_rebuilder.exe
    echo ===================================================
) else (
    echo.
    echo ===================================================
    echo [✘] 打包失败，请检查上方日志。
    echo ===================================================
)
pause

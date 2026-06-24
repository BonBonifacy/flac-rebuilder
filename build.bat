@echo off
echo ===================================================
echo   FLAC Rebuilder PyInstaller打包批处理工具
echo ===================================================
echo.
echo 正在创建打包环境并使用 PyInstaller 进行编译...
echo.
echo 1. 正在编译命令行版本 (flac_rebuilder.py)...
uv run --with pyinstaller --with mutagen --with soundfile --with numpy --with PyQt6 pyinstaller --onefile --console flac_rebuilder.py

echo.
echo 2. 正在编译图形界面版本 (flac_rebuilder_gui.py)...
uv run --with pyinstaller --with mutagen --with soundfile --with numpy --with PyQt6 pyinstaller --onefile --noconsole flac_rebuilder_gui.py

if %ERRORLEVEL% equ 0 (
    echo.
    echo ===================================================
    echo [✔] 所有程序打包成功！
    echo 生成的可执行文件位于:
    echo   - 命令行版: dist\flac_rebuilder.exe
    echo   - 图形界面版: dist\flac_rebuilder_gui.exe
    echo ===================================================
) else (
    echo.
    echo ===================================================
    echo [✘] 打包过程中出现错误，请检查上方日志。
    echo ===================================================
)
pause

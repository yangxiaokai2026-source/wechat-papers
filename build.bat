@echo off
echo WeChat Papers V8 - 打包为 exe
echo.

REM 确保依赖已安装
if not exist ".venv" (
    echo 请先运行 install.bat 安装依赖
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat

REM 打包
pyinstaller --onefile --windowed --name "WeChatPapers" ^
    --add-data "config.json.example;." ^
    --icon=NONE ^
    gui.py

echo.
echo 打包完成！
echo 可执行文件位置: dist\WeChatPapers.exe
echo.
echo 使用前请确保 config.json 已配置好。
echo 将 dist\WeChatPapers.exe 和 config.json 复制到任意位置即可使用。
pause

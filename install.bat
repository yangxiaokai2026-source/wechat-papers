@echo off
echo WeChat Papers V8 - 安装依赖
echo.

REM 创建虚拟环境
uv venv

REM 激活虚拟环境
call .venv\Scripts\activate.bat

REM 安装依赖
uv pip install -r requirements.txt

echo.
echo 安装完成！
echo 1. 编辑 config.json（填写你的微信账号和路径）
echo 2. 双击 WeChatPapers.exe 运行
pause

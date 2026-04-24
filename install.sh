#!/bin/bash
echo "WeChat Papers V8 - 安装依赖 (macOS)"
echo ""

uv venv
source .venv/bin/activate
uv pip install -r requirements.txt

echo ""
echo "安装完成！"
echo "1. 编辑 config.json（填写你的微信账号和路径）"
echo "2. 运行: python gui.py"

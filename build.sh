#!/bin/bash
echo "WeChat Papers V8 - 打包 (macOS)"
echo ""

if [ ! -d ".venv" ]; then
    echo "请先运行 install.sh 安装依赖"
    exit 1
fi

source .venv/bin/activate

pyinstaller --onefile --windowed --name "WeChatPapers" \
    --add-data "config.json.example:." \
    gui.py

echo ""
echo "打包完成！"
echo "可执行文件位置: dist/WeChatPapers"

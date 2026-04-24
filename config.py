"""
config.py - V8 配置管理
从 config.json 加载配置，支持跨平台路径解析

config.json 持久位置：
  - 开发模式：脚本同目录
  - 打包后（PyInstaller）：用户主目录 ~/WeChatPapers_V8/config.json
"""

import os
import json
import sys
import shutil
from pathlib import Path


def _get_config_dir():
    """
    返回配置目录：
    - 打包环境（PyInstaller）：exe 所在目录
    - 开发环境：脚本同目录
    """
    return Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).parent


def _get_config_path():
    """获取 config.json 路径，必要时从打包资源初始化。"""
    config_dir = _get_config_dir()
    config_path = config_dir / "config.json"

    if config_path.exists():
        return config_path

    # 不存在则尝试从程序资源复制
    if getattr(sys, 'frozen', False):
        # 打包环境：从 _MEIPASS 临时目录复制
        try:
            meipass = Path(getattr(sys, '_MEIPASS', ''))
            src = meipass / "config.json"
            if src.exists():
                config_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, config_path)
                return config_path
        except Exception:
            pass
    else:
        # 开发模式：检查同目录 example
        script_dir = Path(__file__).parent
        example = script_dir / "config.json.example"
        if example.exists():
            config_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(example, config_path)
            print(f"[V8] 已在 {config_path} 创建默认配置，请编辑后重新运行。")

    if not config_path.exists():
        raise FileNotFoundError(
            f"config.json 不存在。\n"
            f"请创建: {config_path}"
        )

    return config_path


def expand_path(p):
    """展开 ~ 为用户主目录"""
    return Path(os.path.expanduser(p)).resolve()


def save_config(cfg_dict):
    """保存配置到 config.json（供 GUI 调用）"""
    config_path = _get_config_path()
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(cfg_dict, f, ensure_ascii=False, indent=2)


def load_config():
    config_path = _get_config_path()

    with open(config_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    # 展开路径
    paths = cfg["paths"]
    config = type("Config", (), {})()
    config.config_path = config_path
    config.msg_file_dir = expand_path(paths["msg_file_dir"])

    config.papers_root = expand_path(paths["papers_root"])
    config.academic_dir = config.papers_root / paths["academic_dir"]
    config.other_dir = config.papers_root / paths["other_dir"]
    config.log_file = config.papers_root / paths["log_file"]
    config.hash_store = config.papers_root / paths["hash_store"]

    config.polling_interval = cfg.get("polling_interval", 3)
    config.notification_cooldown = cfg.get("notification_cooldown", 60)
    config.enable_notifications = cfg.get("enable_notifications", True)

    gui_cfg = cfg.get("gui", {})
    config.gui_minimize_to_tray = gui_cfg.get("minimize_to_tray", True)
    config.gui_log_refresh_ms = gui_cfg.get("log_refresh_ms", 500)
    config.gui_window_width = gui_cfg.get("window_width", 800)
    config.gui_window_height = gui_cfg.get("window_height", 600)

    # 创建目录
    config.academic_dir.mkdir(parents=True, exist_ok=True)
    config.other_dir.mkdir(parents=True, exist_ok=True)

    return config

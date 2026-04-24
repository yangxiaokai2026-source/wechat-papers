"""
monitor_engine.py - V8 监控引擎
轮询检测 + MD5 去重 + 文件处理
"""

import os
import time
import json
import logging
import threading
import subprocess
from pathlib import Path

from config import load_config
from detector import md5_file, classify_pdf

cfg = load_config()

# 日志设置
logger = logging.getLogger("v8")
logger.setLevel(logging.INFO)
_fh = logging.FileHandler(cfg.log_file, encoding="utf-8")
_fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.addHandler(_fh)

# 内存日志缓存（供 GUI 读取）
_log_buffer = []
_log_lock = threading.Lock()
MAX_LOG_LINES = 500

class GuiHandler(logging.Handler):
    def emit(self, record):
        msg = self.format(record)
        with _log_lock:
            _log_buffer.append(msg)
            if len(_log_buffer) > MAX_LOG_LINES:
                _log_buffer[:] = _log_buffer[-MAX_LOG_LINES:]

logger.addHandler(GuiHandler())

# ========== MD5 去重 ==========\n
processed_hashes = set()
_skipped_files = set()  # 记录已被处理/SKIP的文件路径，避免重复日志

def load_hashes():
    global processed_hashes
    if cfg.hash_store.exists():
        with open(cfg.hash_store, 'r') as f:
            processed_hashes.update(f.read().split())
    for d in [cfg.academic_dir, cfg.other_dir]:
        for p in list(d.glob('*.pdf')):
            h = md5_file(p)
            if h:
                processed_hashes.add(h)
    # 标记源目录中已处理过的文件为 skipped
    if cfg.msg_file_dir.exists():
        for dirpath, _, filenames in os.walk(cfg.msg_file_dir):
            for fname in filenames:
                if fname.lower().endswith('.pdf'):
                    fpath = Path(dirpath) / fname
                    h = md5_file(fpath)
                    if h and h in processed_hashes:
                        _skipped_files.add(fpath)

# ========== 通知 ==========

_notification_lock = threading.Lock()
_last_notification = 0

def notify(title, message):
    global _last_notification
    if not cfg.enable_notifications:
        return
    with _notification_lock:
        now = time.time()
        if now - _last_notification < cfg.notification_cooldown:
            return
        _last_notification = now
    try:
        platform = os.uname().sysname if hasattr(os, 'uname') else ''
        if platform == 'Darwin':  # macOS
            cmd = ['osascript', '-e',
                   f'display notification "{message}" with title "{title}" sound name "Glass"']
            subprocess.run(cmd, capture_output=True, timeout=3)
        elif platform == 'Linux':
            subprocess.run(['notify-send', title, message], capture_output=True, timeout=3)
        # Windows: 通过 GUI 显示，不调用系统通知
    except Exception as e:
        logger.warning(f"通知失败: {e}")

# ========== 元数据写入 ==========

def write_metadata(name, meta):
    base = Path(name).stem
    meta_path = cfg.academic_dir / f"{base}_metadata.json"
    meta["filename"] = name
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

# ========== 核心处理 ==========

def process_pdf(src):
    """处理单个 PDF 文件"""
    src = Path(src)

    # 等待文件写入完成
    for _ in range(5):
        time.sleep(0.5)
        if src.exists() and src.is_file():
            break
    if not src.exists():
        return

    # MD5 去重
    md5_val = md5_file(src)
    if md5_val and md5_val in processed_hashes:
        logger.info(f"SKIP 重复: {src.name}")
        _skipped_files.add(src)
        return
    if md5_val:
        processed_hashes.add(md5_val)
        with open(cfg.hash_store, 'a') as f:
            f.write(md5_val + '\n')

    # 4层检测
    is_academic, layer, meta = classify_pdf(src)

    # 移动文件
    dest_dir = cfg.academic_dir if is_academic else cfg.other_dir
    dest_path = dest_dir / src.name
    try:
        import shutil
        import stat
        # WeChat 下载的文件可能是只读的，先加写权限
        try:
            current_mode = src.stat().st_mode
            if not (current_mode & stat.S_IWUSR):
                src.chmod(current_mode | stat.S_IWUSR)
                logger.info(f"CHMOD {src.name} (was read-only)")
        except Exception:
            pass  # 权限操作失败不阻塞
        shutil.move(str(src), str(dest_path))
        status = f"论文[Layer{layer}]" if is_academic else "其他"
        logger.info(f"SAVED {src.name} ({status})")
        if is_academic:
            notify("新论文入库", f"{src.name}")

        # 写入元数据
        if meta:
            meta["detection_layer"] = layer
            write_metadata(dest_path.name, meta)
        elif is_academic:
            fallback = {
                "status": "keyword_only", "confidence": "none",
                "detection_layer": layer, "filename": dest_path.name,
                "title": "unknown",
                "note": "仅通过关键词检测，未能从OpenAlex获取元数据"
            }
            write_metadata(dest_path.name, fallback)
    except Exception as e:
        logger.error(f"移动失败 {src.name}: {e}")
        _skipped_files.add(src)

# ========== 轮询监控 ==========

_recent_files = {}
_run_flag = threading.Event()
# _run_flag starts cleared — only set when start_monitoring() is called

def get_all_pdfs():
    all_pdfs = []
    if not cfg.msg_file_dir.exists():
        return all_pdfs
    for dirpath, _, filenames in os.walk(cfg.msg_file_dir):
        for fname in filenames:
            if fname.lower().endswith('.pdf'):
                fpath = Path(dirpath) / fname
                try:
                    all_pdfs.append((str(fpath), fpath.stat().st_mtime))
                except:
                    pass
    return all_pdfs

def poll_loop():
    """轮询主循环"""
    while _run_flag.is_set():
        time.sleep(cfg.polling_interval)
        if not _run_flag.is_set():
            break
        try:
            all_pdfs = get_all_pdfs()
            now = time.time()
            for filepath_str, mtime in all_pdfs:
                src = Path(filepath_str)
                # 跳过正在写入的文件（修改时间 < 15秒）
                if now - mtime < 15:
                    continue
                # 跳过目标目录
                if src.parent == cfg.academic_dir or src.parent == cfg.other_dir:
                    continue
                # 跳过已被处理/SKIP的文件
                if src in _skipped_files:
                    continue
                # 去重（3秒内不重复处理）
                if _recent_files.get(src, 0) and now - _recent_files[src] < 3:
                    continue
                _recent_files[src] = now
                logger.info(f"POLL 发现: {src.name}")
                process_pdf(src)
        except Exception as e:
            logger.error(f"轮询错误: {e}")

# ========== GUI 接口 ==========

def start_monitoring():
    """启动监控（由 GUI 调用）"""
    global _poll_thread
    _run_flag.set()
    _poll_thread = threading.Thread(target=poll_loop, daemon=True)
    _poll_thread.start()
    logger.info(f"监控已启动 - 目录: {cfg.msg_file_dir}")

def stop_monitoring():
    """停止监控（由 GUI 调用）"""
    _run_flag.clear()
    logger.info("监控已停止")

def is_running():
    """监控是否运行中"""
    return _run_flag.is_set()

def get_log_lines():
    """获取日志行（供 GUI 显示）"""
    with _log_lock:
        return list(_log_buffer)

def clear_log():
    """清空内存日志"""
    with _log_lock:
        _log_buffer.clear()

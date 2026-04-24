"""
gui.py - V8 GUI 主入口
使用 tkinter（Python 内置，无需额外安装）
跨平台支持：Windows / macOS / Linux
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import threading
import json
import os
from pathlib import Path
import sys

from config import load_config, expand_path
from monitor_engine import (
    load_hashes, start_monitoring, stop_monitoring,
    is_running, get_log_lines, clear_log
)

cfg = load_config()

class WeChatPapersApp:
    def __init__(self, root):
        self.root = root
        self.root.title("WeChat Papers Monitor V8")
        self.root.geometry(f"{cfg.gui_window_width}x{cfg.gui_window_height}")
        self.root.minsize(600, 400)

        # 状态变量
        self.status_var = tk.StringVar(value="未启动")
        self.running = False

        self.last_log_count = 0
        self._build_ui()
        self._load_stats()
        self._start_refresh_timer()
        self._toggle_monitor()  # 启动时自动开始监控

    def _build_ui(self):
        # ===== 顶部工具栏 =====
        toolbar = ttk.Frame(self.root, padding=10)
        toolbar.pack(fill=tk.X)

        # 状态指示
        self.status_indicator = tk.Canvas(toolbar, width=16, height=16, highlightthickness=0)
        self.status_indicator.pack(side=tk.LEFT, padx=5)
        self._update_indicator()

        self.status_label = ttk.Label(toolbar, textvariable=self.status_var, font=("", 10))
        self.status_label.pack(side=tk.LEFT, padx=5)

        ttk.Label(toolbar, text="  |  ", font=("", 10)).pack(side=tk.LEFT)

        # 启动/停止按钮
        self.btn_toggle = ttk.Button(toolbar, text="启动监控", command=self._toggle_monitor)
        self.btn_toggle.pack(side=tk.LEFT, padx=5)

        # 配置按钮
        self.btn_config = ttk.Button(toolbar, text="配置", command=self._edit_config)
        self.btn_config.pack(side=tk.LEFT, padx=5)

        # 日志按钮
        self.btn_clear_log = ttk.Button(toolbar, text="清空日志", command=self._clear_log)
        self.btn_clear_log.pack(side=tk.LEFT, padx=5)

        # 统计信息
        ttk.Label(toolbar, text="  |  ", font=("", 10)).pack(side=tk.LEFT)
        self.stat_var = tk.StringVar(value="论文: 0 | 其他: 0")
        ttk.Label(toolbar, textvariable=self.stat_var).pack(side=tk.LEFT, padx=5)

        # ===== 主体区域（左右分栏） =====
        main = ttk.Frame(self.root)
        main.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # 左侧：日志
        log_frame = ttk.LabelFrame(main, text="  实时日志  ", padding=5)
        log_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, state=tk.DISABLED,
                                                   font=("", 9), bg="#1e1e1e", fg="#d4d4d4")
        self.log_text.pack(fill=tk.BOTH, expand=True)

        # 日志颜色标签
        self.log_text.tag_config("info", foreground="#4ec9b0")
        self.log_text.tag_config("saved", foreground="#9cdcfe")
        self.log_text.tag_config("error", foreground="#f44747")
        self.log_text.tag_config("warn", foreground="#dcdcaa")
        self.log_text.tag_config("skip", foreground="#808080")

        # 右侧：文件列表
        file_frame = ttk.LabelFrame(main, text="  已处理文件  ", padding=5)
        file_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))

        cols = ("name", "layer", "doi", "author", "journal", "time")
        self.file_tree = ttk.Treeview(file_frame, columns=cols, show="headings", height=10)
        self.file_tree.heading("name", text="文件名")
        self.file_tree.heading("layer", text="层")
        self.file_tree.heading("doi", text="DOI")
        self.file_tree.heading("author", text="作者")
        self.file_tree.heading("journal", text="期刊")
        self.file_tree.heading("time", text="时间")
        self.file_tree.column("name", width=180, minwidth=100)
        self.file_tree.column("layer", width=40, minwidth=30)
        self.file_tree.column("doi", width=180, minwidth=100)
        self.file_tree.column("author", width=120, minwidth=60)
        self.file_tree.column("journal", width=120, minwidth=60)
        self.file_tree.column("time", width=100, minwidth=60)
        self.file_tree.pack(fill=tk.BOTH, expand=True)

        # 右键菜单
        self.file_tree.bind("<Button-3>", self._file_context_menu)
        self.file_tree.bind("<Button-2>", self._file_context_menu)  # macOS 中键
        self._context_menu = tk.Menu(self.file_tree, tearoff=0)
        self._context_menu.add_command(label="打开文件", command=self._open_selected_file)
        self._context_menu.add_command(label="打开文件夹", command=self._open_file_folder)

        # 刷新文件列表按钮
        btn_refresh = ttk.Button(file_frame, text="刷新列表", command=self._load_stats)
        btn_refresh.pack(fill=tk.X, pady=5)

        # ===== 底部状态栏 =====
        status_bar = ttk.Frame(self.root, padding=(10, 5))
        status_bar.pack(fill=tk.X)

        self.path_var = tk.StringVar(value=f"监控: {cfg.msg_file_dir}")
        ttk.Label(status_bar, textvariable=self.path_var, font=("", 8), foreground="gray").pack(side=tk.LEFT)

        self.version_var = tk.StringVar(value="V8.0")
        ttk.Label(status_bar, textvariable=self.version_var, font=("", 8), foreground="gray").pack(side=tk.RIGHT)

    def _update_indicator(self):
        if is_running():
            self.status_indicator.delete("all")
            self.status_indicator.create_oval(2, 2, 14, 14, fill="#00ff00")
            self.status_var.set("监控中")
        else:
            self.status_indicator.delete("all")
            self.status_indicator.create_oval(2, 2, 14, 14, fill="#808080")
            self.status_var.set("未启动")

    def _toggle_monitor(self):
        if not is_running():
            load_hashes()
            start_monitoring()
            self.btn_toggle.config(text="停止监控")
            self.status_var.set("正在启动...")
            self._update_indicator()
        else:
            stop_monitoring()
            self.btn_toggle.config(text="启动监控")
            self._update_indicator()

    def _clear_log(self):
        clear_log()
        self._refresh_log_view_full()

    def _refresh_log_view(self):
        lines = get_log_lines()
        new_lines = lines[self.last_log_count:]
        if not new_lines and self.last_log_count == 0:
            # 首次加载，从文件日志加载
            lines = self._load_file_log()
            new_lines = lines
        if not new_lines:
            return

        self.log_text.config(state=tk.NORMAL)
        for line in new_lines:
            self.log_text.insert(tk.END, line + "\n")
            lower = line.lower()
            if "saved" in lower:
                self.log_text.tag_add("saved", f"end-2lines", "end-1line")
            elif "error" in lower or "失败" in line:
                self.log_text.tag_add("error", f"end-2lines", "end-1line")
            elif "warn" in lower or "警告" in line:
                self.log_text.tag_add("warn", f"end-2lines", "end-1line")
            elif "skip" in lower:
                self.log_text.tag_add("skip", f"end-2lines", "end-1line")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
        self.last_log_count = len(lines)

    def _refresh_log_view_full(self):
        """全量刷新（用于清空日志后）"""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        lines = get_log_lines()
        if not lines:
            lines = self._load_file_log()
        for line in lines:
            self.log_text.insert(tk.END, line + "\n")
            lower = line.lower()
            if "saved" in lower:
                self.log_text.tag_add("saved", f"end-2lines", "end-1line")
            elif "error" in lower or "失败" in line:
                self.log_text.tag_add("error", f"end-2lines", "end-1line")
            elif "warn" in lower or "警告" in line:
                self.log_text.tag_add("warn", f"end-2lines", "end-1line")
            elif "skip" in lower:
                self.log_text.tag_add("skip", f"end-2lines", "end-1line")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
        self.last_log_count = len(lines)

    def _load_file_log(self):
        """从文件日志加载最近500行（内存日志为空时的后备）"""
        log_path = cfg.log_file
        try:
            if log_path.exists():
                with open(log_path, 'r', encoding='utf-8') as f:
                    all_lines = f.read().strip().split('\n')
                return [l for l in all_lines[-500:] if l]
        except Exception:
            pass
        return []

    def _load_stats(self):
        self.file_tree.delete(*self.file_tree.get_children())
        from datetime import datetime

        def _scan(directory, layer_default="-"):
            for f in sorted(directory.glob("*.pdf"), key=lambda p: p.stat().st_mtime, reverse=True)[:50]:
                layer = layer_default
                doi, author, journal = "", "", ""
                meta_path = directory / f"{f.stem}_metadata.json"
                if meta_path.exists():
                    try:
                        with open(meta_path, 'r', encoding='utf-8') as mf:
                            meta = json.load(mf)
                        layer = f"L{meta.get('detection_layer', '?')}"
                        doi = meta.get('doi', '') or ''
                        authors = meta.get('authors', [])
                        author = ', '.join(authors[:2]) if authors else (meta.get('author', '') or '')
                        if len(authors) > 2:
                            author += ', et al.'
                        journal = meta.get('journal', '') or ''
                    except:
                        pass
                mtime = f.stat().st_mtime
                t = datetime.fromtimestamp(mtime).strftime("%m-%d %H:%M")
                self.file_tree.insert("", "end", values=(f.name, layer, doi, author, journal, t))

        # 学术论文
        _scan(cfg.academic_dir)
        # 其他文件
        _scan(cfg.other_dir, layer_default="-")

        # 更新统计
        academic_count = len(list(cfg.academic_dir.glob("*.pdf")))
        other_count = len(list(cfg.other_dir.glob("*.pdf")))
        self.stat_var.set(f"论文: {academic_count} | 其他: {other_count}")

    def _start_refresh_timer(self):
        self.root.after(cfg.gui_log_refresh_ms, self._periodic_refresh)

    def _periodic_refresh(self):
        self._refresh_log_view()
        self._update_indicator()
        self.root.after(cfg.gui_log_refresh_ms, self._periodic_refresh)

    def _edit_config(self):
        from config import save_config, _get_config_path
        win = tk.Toplevel(self.root)
        win.title("编辑配置")
        win.geometry("550x450")

        config_path = _get_config_path()

        # 显示实际路径
        ttk.Label(win, text=f"配置文件: {config_path}",
                  font=("", 8), foreground="gray").pack(pady=(5, 0), padx=10)

        text = scrolledtext.ScrolledText(win, wrap=tk.WORD, font=("", 10))
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                text.insert(1.0, f.read())
        else:
            text.insert(1.0, f"# 配置文件不存在: {config_path}\n# 请创建后重新打开")

        btn_frame = ttk.Frame(win)
        btn_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(btn_frame, text="修改后请重启监控程序生效", foreground="gray").pack(side=tk.LEFT)

        def save_and_close():
            content = text.get(1.0, tk.END)
            try:
                # 验证 JSON 格式
                data = json.loads(content)
                save_config(data)
                messagebox.showinfo("配置", f"配置已保存到:\n{config_path}\n\n请重启程序使新配置生效。")
                win.destroy()
            except json.JSONDecodeError as e:
                messagebox.showerror("配置错误", f"JSON 格式有误：\n{e}")

        ttk.Button(btn_frame, text="保存", command=save_and_close).pack(side=tk.RIGHT)
        ttk.Button(btn_frame, text="取消", command=win.destroy).pack(side=tk.RIGHT, padx=5)

    def _file_context_menu(self, event):
        item = self.file_tree.identify_row(event.y)
        if item:
            self.file_tree.selection_set(item)
            self._context_menu.tk_popup(event.x_root, event.y_root)

    def _open_selected_file(self):
        item = self.file_tree.selection()
        if not item:
            return
        name = self.file_tree.item(item[0])['values'][0]
        # 查找文件
        for d in [cfg.academic_dir, cfg.other_dir]:
            fpath = d / name
            if fpath.exists():
                # 用系统默认程序打开
                if sys.platform == 'darwin':
                    os.system(f'open "{fpath}"')
                elif sys.platform == 'win32':
                    os.startfile(str(fpath))
                else:
                    os.system(f'xdg-open "{fpath}"')
                return
        messagebox.showwarning("提示", "文件不存在")

    def _open_file_folder(self):
        item = self.file_tree.selection()
        if not item:
            return
        name = self.file_tree.item(item[0])['values'][0]
        for d in [cfg.academic_dir, cfg.other_dir]:
            fpath = d / name
            if fpath.exists():
                if sys.platform == 'darwin':
                    os.system(f'open -R "{fpath}"')
                elif sys.platform == 'win32':
                    os.system(f'explorer /select,"{fpath}"')
                else:
                    os.system(f'xdg-open "{d}"')
                return
        messagebox.showwarning("提示", "文件不存在")

def main():
    root = tk.Tk()
    # 高 DPI 支持（Windows）
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

    app = WeChatPapersApp(root)

    # 关闭时停止监控
    def on_close():
        if is_running():
            if messagebox.askokcancel("退出", "监控仍在运行，确定要退出吗？"):
                stop_monitoring()
                root.destroy()
        else:
            root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()

if __name__ == "__main__":
    main()

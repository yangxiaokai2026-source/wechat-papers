# WeChat Papers Monitor

自动从微信缓存中检测学术 PDF 论文，分类整理并提取元数据（标题、作者、DOI、摘要等）。

## 功能

- 轮询微信文件缓存目录，自动发现新 PDF
- 4 层学术论文检测（文件名 DOI → PDF 内 DOI → 关键词 → OpenAlex 元数据检索）
- MD5 去重，避免重复下载
- 自动分类到 `Academic_Papers` / `Other_PDFs`
- GUI 实时监控面板，日志刷新与统计

## 安装

### 前置要求

- **Python 3.9+**
- **uv**（快速 Python 包管理工具）

  安装 uv：

  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```

### 步骤

1. **克隆项目**

   ```bash
   git clone https://github.com/yangxiaokai2026-source/wechat-papers.git
   cd wechat-papers
   ```

2. **创建虚拟环境并安装依赖**

   ```bash
   uv venv
   uv pip install pdfplumber watchdog
   ```

3. **配置**

   复制示例配置文件：

   ```bash
   cp config.json.example config.json
   ```

   编辑 `config.json`，修改 `paths.msg_file_dir` 为你的微信文件缓存路径：

   - **macOS**：`~/Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files/你的微信ID/msg/file`
   - **Windows**：`C:\Users\你的用户名\Documents\WeChat Files\你的微信ID\FileStorage\File`

   你的微信 ID（`wxid_xxx`）可在微信文件路径中找到。

4. **运行**

   ```bash
   uv run python gui.py
   ```

   启动后可点击 **启动监控** 按钮开始。

## 微信设置

为了让系统正确检测群文件中下载的 PDF，需要确保：

1. 微信中 **开启文件自动下载**（设置 → 文件管理 → 勾选"自动下载"）
2. 知道你的 **微信账号 ID**（即 `wxid_xxx`），用于配置 `msg_file_dir` 路径
   - macOS：打开 Finder → 前往 → 前往文件夹，输入 `~/Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files/`，里面只有一个文件夹就是你的微信 ID
   - Windows：打开微信文件目录（微信设置 → 文件管理 → 打开文件夹），查看子文件夹名称

## 配置文件说明

| 配置项 | 说明 |
|--------|------|
| `paths.msg_file_dir` | 微信文件缓存目录（必须修改） |
| `paths.papers_root` | 论文保存根目录（默认 `~/Documents/WeChatPapers`） |
| `paths.academic_dir` | 学术论文子目录名（默认 `Academic_Papers`） |
| `paths.other_dir` | 非学术 PDF 子目录名（默认 `Other_PDFs`） |
| `polling_interval` | 轮询间隔（秒，默认 3） |
| `enable_notifications` | 是否启用桌面通知 |
| `gui.log_refresh_ms` | GUI 日志刷新间隔（毫秒） |

## 可选：打包为独立应用

使用 PyInstaller 打包为单文件可执行文件：

```bash
uv pip install pyinstaller
pyinstaller --onefile --windowed --name WeChatPapers gui.py
```

打包后的文件在 `dist/` 目录中。

## License

MIT

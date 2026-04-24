# WeChat Papers Monitor V8

## 快速开始

### Windows

1. 双击 `install.bat` 安装依赖（约 1 分钟）
2. 编辑 `config.json`，修改：
   - `wechat_account_id` → 你的微信账号 ID
   - `paths.base_wechat` → 微信文件路径
     - Windows 示例: `C:\Users\你的用户名\Documents\WeChat Files`
3. （可选）双击 `build.bat` 打包成 exe
4. 双击 `WeChatPapers.exe` 运行

### macOS

1. `bash install.sh` 安装依赖
2. 编辑 `config.json`
3. （可选）`bash build.sh` 打包成 app
4. 运行 `python gui.py` 或点击打包好的应用

### 配置文件说明

`config.json` 中的关键配置：

| 配置项 | 说明 |
|--------|------|
| wechat_account_id | 微信账号ID，在 WeChat 文件路径中 |
| paths.base_wechat | WeChat 文件根目录 |
| papers_root | 论文保存根目录 |
| polling_interval | 轮询间隔（秒）|
| enable_notifications | 是否启用桌面通知 |

### 跨平台分发

在一台 Windows 机器上 build 后，将 `dist/WeChatPapers.exe` + `config.json` 复制到任意 Windows 机器即可使用，无需安装 Python。

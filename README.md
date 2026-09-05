# 🐧 MemeBox — 表情包 & 剪贴板聚合助手

一个常驻 Windows 系统托盘的聚合工具：**表情包快速调用** + **剪贴板历史记录**，采用 HTML/CSS 前端 + PyQt5 WebEngine 壳架构，实现 Win11 级动效体验。

## ✨ 功能特性

### 表情包
- 📥 两种导入方式：本地文件夹批量导入 / 直接粘贴剪贴板图片
- 🖱️ 点击表情即复制到剪贴板（CF_DIB 格式，QQ/微信可直接粘贴）
- ⚡ 全局热键 `Ctrl+Shift+V` 一键「粘贴 + 回车」发送
- 🔍 实时搜索过滤
- 🖼️ GIF 动图完整支持（CF_HDROP 保留动画）

### 剪贴板历史
- 📋 后台自动监听，文本和图片都记录
- 💾 图片以 PNG 长期存盘，重启不丢
- 🔄 智能去重：重复复制自动提升到最前
- 📌 支持置顶、单条删除、一键清空（保留置顶）
- 🗂️ 最多保留 500 条，可配置

### 系统集成
- 🔔 系统托盘常驻，单击/双击呼出
- 🔁 开机自启（注册表 Run 项，启动后安静驻留托盘）
- 🪟 无边框窗口，8 向边缘拖拽自由缩放
- 📁 自定义数据存储目录
- ⚙️ 完整设置面板（存储位置 / 自启 / 监听 / 自动隐藏）

### Win11 动效
- Mica 亚克力毛玻璃（`backdrop-filter` 40px 模糊）
- 窗口弹出动画、卡片弹性悬浮、点击涟漪
- 表情卡片交错浮现、页面切换过渡
- 响应式布局，窗口任意缩放自适应

## 📦 下载使用

直接到 [Releases](../../releases) 下载打包好的 `QQ表情包助手.exe`，双击即用，无需安装 Python。

## 🛠️ 从源码运行

```bash
# 克隆
git clone https://github.com/kamidanahida/memebot.git
cd memebot

# 安装依赖
pip install -r requirements.txt

# 运行
python main.py
```

## 📦 自行打包

```bash
pyinstaller --noconfirm --onefile --windowed \
  --name "QQ表情包助手" --icon app.ico \
  --add-data "ui;ui" \
  --hidden-import win32clipboard --hidden-import win32con \
  main.py
```

产物在 `dist/` 目录。

## 🏗️ 技术架构

```
ui/index.html  ←── QWebChannel 桥接 ──→  main.py (Python)
 (Win11 动效)                             (托盘/剪贴板/热键/导入/自启)
```

| 模块 | 职责 |
|------|------|
| `main.py` | 主入口、QWebEngineView 壳、托盘、桥接、剪贴板监听 |
| `ui/index.html` | 全部 UI 与动效（纯 HTML/CSS/JS，无框架） |
| `clipboard_history.py` | 剪贴板历史持久化（JSONL + 图片文件） |
| `clipboard_sender.py` | CF_DIB / CF_HDROP 剪贴板写入、模拟粘贴发送 |
| `config.py` | 配置管理、自定义数据目录 |
| `autostart.py` | Windows 注册表开机自启 |

## 📂 数据存放

默认位于 `~/.qq_meme_tray/`（可在设置中更改）：

```
<数据目录>/
├── memes/              表情包图片
├── history/
│   ├── items.jsonl     剪贴板历史元数据
│   └── images/         剪贴板图片
└── config.json         配置文件（固定位置）
```

## ⚠️ 注意事项

- 全局热键依赖键盘钩子，部分安全软件可能拦截，请加入白名单
- QQ 收藏的表情没有官方导出接口，需先保存为图片文件再导入

## 📄 许可证

[MIT License](LICENSE)

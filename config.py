"""配置管理模块：负责数据存储目录、热键设置等持久化配置。

支持自定义数据目录（data_dir），默认 ~/.qq_meme_tray。
目录结构：
  <data_dir>/memes/            表情包图片
  <data_dir>/history/items.jsonl   剪贴板历史元数据
  <data_dir>/history/images/       剪贴板图片长期保存
"""
import json
import os

APP_NAME = "QQ表情包助手"

# 默认数据根目录
DEFAULT_BASE_DIR = os.path.join(os.path.expanduser("~"), ".qq_meme_tray")
# 配置文件始终固定在默认位置（记录 data_dir 指向）
CONFIG_PATH = os.path.join(DEFAULT_BASE_DIR, "config.json")

IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp")

DEFAULT_CONFIG = {
    "send_hotkey": "ctrl+shift+v",
    "auto_hide_on_click": True,
    "columns": 4,
    "thumb_size": 120,
    # 自定义数据目录（None 表示用默认）
    "data_dir": None,
    # 剪贴板历史最大记录数
    "history_limit": 500,
    # 是否开启剪贴板监听
    "watch_clipboard": True,
}

# 运行时动态计算的目录（模块加载时根据 config 初始化）
BASE_DIR = DEFAULT_BASE_DIR
MEME_DIR = os.path.join(BASE_DIR, "memes")
HISTORY_DIR = os.path.join(BASE_DIR, "history")
HISTORY_IMG_DIR = os.path.join(HISTORY_DIR, "images")
HISTORY_INDEX = os.path.join(HISTORY_DIR, "items.jsonl")


def _apply_data_dir(path):
    """根据 data_dir 重算所有目录。"""
    global BASE_DIR, MEME_DIR, HISTORY_DIR, HISTORY_IMG_DIR, HISTORY_INDEX
    BASE_DIR = path
    MEME_DIR = os.path.join(BASE_DIR, "memes")
    HISTORY_DIR = os.path.join(BASE_DIR, "history")
    HISTORY_IMG_DIR = os.path.join(HISTORY_DIR, "images")
    HISTORY_INDEX = os.path.join(HISTORY_DIR, "items.jsonl")


def load_config():
    """读取配置，缺失的键用默认值补齐。"""
    cfg = dict(DEFAULT_CONFIG)
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                cfg.update(data)
        except (json.JSONDecodeError, OSError):
            pass
    # 应用自定义数据目录
    dd = cfg.get("data_dir")
    if dd and os.path.isdir(dd):
        _apply_data_dir(dd)
    else:
        _apply_data_dir(DEFAULT_BASE_DIR)
    return cfg


def save_config(cfg):
    """保存配置。"""
    try:
        os.makedirs(DEFAULT_BASE_DIR, exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


def set_data_dir(path):
    """设置自定义数据目录并保存配置。返回是否成功。"""
    if not path or not os.path.isdir(path):
        return False
    cfg = load_config()
    cfg["data_dir"] = path
    save_config(cfg)
    _apply_data_dir(path)
    return True


def ensure_dirs():
    """确保所有应用目录存在。"""
    os.makedirs(MEME_DIR, exist_ok=True)
    os.makedirs(HISTORY_IMG_DIR, exist_ok=True)
    return BASE_DIR


def list_memes():
    """列出表情目录下所有图片文件，返回完整路径列表。"""
    if not os.path.isdir(MEME_DIR):
        return []
    items = []
    for name in os.listdir(MEME_DIR):
        if name.lower().endswith(IMAGE_EXTS):
            items.append(os.path.join(MEME_DIR, name))
    items.sort(key=lambda p: os.path.basename(p).lower())
    return items


# 模块加载时初始化目录
load_config()
ensure_dirs()

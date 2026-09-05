"""剪贴板历史模块：后台监听剪贴板变化，长期保存文本和图片。

存储结构（位于 config.HISTORY_DIR）：
  items.jsonl   每行一条 JSON：{id, type, content, file, time, pinned}
  images/       图片文件（PNG 长期保存，文件名 = id.png）
"""
import json
import os
import time
import base64
import hashlib

import config


def _now():
    return time.time()


def _gen_id(content_hash):
    return f"{int(_now() * 1000)}_{content_hash[:8]}"


def _hash_text(text):
    return hashlib.md5(text.encode("utf-8", "ignore")).hexdigest()


def _hash_image(image_path):
    try:
        with open(image_path, "rb") as f:
            return hashlib.md5(f.read(65536)).hexdigest()
    except OSError:
        return str(_now())


class ClipboardHistory:
    """剪贴板历史管理器。"""

    def __init__(self):
        self.items = []
        self._last_hash = None
        self.load()

    # ---------- 持久化 ----------
    def load(self):
        """从 items.jsonl 加载历史。"""
        self.items = []
        if not os.path.exists(config.HISTORY_INDEX):
            return
        try:
            with open(config.HISTORY_INDEX, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        item = json.loads(line)
                        self.items.append(item)
                    except json.JSONDecodeError:
                        continue
        except OSError:
            pass

    def _save(self):
        """全量写回 items.jsonl。"""
        try:
            os.makedirs(config.HISTORY_DIR, exist_ok=True)
            with open(config.HISTORY_INDEX, "w", encoding="utf-8") as f:
                for item in self.items:
                    f.write(json.dumps(item, ensure_ascii=False) + "\n")
        except OSError:
            pass

    # ---------- 记录 ----------
    def add_text(self, text):
        """记录一条文本剪贴板内容。"""
        text = text.strip()
        if not text:
            return False
        h = _hash_text(text)
        if h == self._last_hash:
            return False
        # 去重：已存在相同文本则提升到最前
        for idx, it in enumerate(self.items):
            if it.get("type") == "text" and it.get("hash") == h:
                it["time"] = _now()
                self.items.insert(0, self.items.pop(idx))
                self._last_hash = h
                self._save()
                return True
        item = {
            "id": _gen_id(h),
            "type": "text",
            "content": text,
            "hash": h,
            "time": _now(),
            "pinned": False,
        }
        self.items.insert(0, item)
        self._last_hash = h
        self._trim()
        self._save()
        return True

    def add_image(self, qimage):
        """记录一条图片剪贴板内容（QImage 保存为 PNG）。"""
        try:
            ts = int(_now() * 1000)
            tmp_path = os.path.join(config.HISTORY_IMG_DIR, f"tmp_{ts}.png")
            os.makedirs(config.HISTORY_IMG_DIR, exist_ok=True)
            qimage.save(tmp_path, "PNG")
            h = _hash_image(tmp_path)
            if h == self._last_hash:
                os.remove(tmp_path)
                return False
            # 去重：相同图片提升到最前
            for idx, it in enumerate(self.items):
                if it.get("type") == "image" and it.get("hash") == h:
                    it["time"] = _now()
                    self.items.insert(0, self.items.pop(idx))
                    self._last_hash = h
                    os.remove(tmp_path)
                    self._save()
                    return True
            item_id = _gen_id(h)
            final_path = os.path.join(config.HISTORY_IMG_DIR, f"{item_id}.png")
            os.replace(tmp_path, final_path)
            item = {
                "id": item_id,
                "type": "image",
                "file": final_path,
                "hash": h,
                "time": _now(),
                "pinned": False,
            }
            self.items.insert(0, item)
            self._last_hash = h
            self._trim()
            self._save()
            return True
        except Exception:
            return False

    def _trim(self):
        """按 history_limit 裁剪（保留置顶项）。"""
        limit = config.load_config().get("history_limit", 500)
        if len(self.items) <= limit:
            return
        pinned = [i for i in self.items if i.get("pinned")]
        normal = [i for i in self.items if not i.get("pinned")]
        removed = normal[limit - len(pinned):]
        for it in removed:
            if it.get("type") == "image" and it.get("file"):
                try:
                    os.remove(it["file"])
                except OSError:
                    pass
        self.items = pinned + normal[:limit - len(pinned)]

    # ---------- 查询 ----------
    def get_items(self, limit=200):
        """返回前端可用的历史列表（新→旧）。"""
        result = []
        for it in self.items[:limit]:
            entry = {
                "id": it["id"],
                "type": it["type"],
                "time": it["time"],
                "pinned": it.get("pinned", False),
            }
            if it["type"] == "text":
                entry["content"] = it["content"]
            else:
                entry["dataUrl"] = image_file_to_data_url(it.get("file"))
            result.append(entry)
        return result

    def find(self, item_id):
        for it in self.items:
            if it["id"] == item_id:
                return it
        return None

    def delete(self, item_id):
        """删除一条记录。"""
        it = self.find(item_id)
        if not it:
            return False
        if it.get("type") == "image" and it.get("file"):
            try:
                os.remove(it["file"])
            except OSError:
                pass
        self.items = [i for i in self.items if i["id"] != item_id]
        self._save()
        return True

    def toggle_pin(self, item_id):
        it = self.find(item_id)
        if not it:
            return False
        it["pinned"] = not it.get("pinned", False)
        # 置顶项排到最前
        self.items.sort(key=lambda x: (not x.get("pinned", False), -x["time"]))
        self._save()
        return it["pinned"]

    def clear(self):
        """清空全部历史（保留置顶）。"""
        for it in self.items:
            if not it.get("pinned") and it.get("type") == "image" and it.get("file"):
                try:
                    os.remove(it["file"])
                except OSError:
                    pass
        self.items = [i for i in self.items if i.get("pinned")]
        self._save()


def image_file_to_data_url(path, size=160):
    """图片文件转 base64 dataURL 缩略图。"""
    if not path or not os.path.exists(path):
        return ""
    try:
        from PIL import Image
        import io
        img = Image.open(path)
        img.thumbnail((size, size), Image.LANCZOS)
        if img.mode == "P":
            img = img.convert("RGBA")
        elif img.mode != "RGBA":
            img = img.convert("RGBA")
        buf = io.BytesIO()
        img.save(buf, "PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        return f"data:image/png;base64,{b64}"
    except Exception:
        return ""

"""QQ 表情包助手 —— Win11 动效版（QWebEngineView 壳 + HTML/CSS 前端）。

架构：
- 前端 ui/index.html：纯 HTML/CSS/JS 实现 Win11 动效（毛玻璃、淡入、悬浮、涟漪、惯性滚动）
- 后端 main.py：系统托盘、剪贴板、文件导入、全局热键
- 通信：QWebChannel 桥接（JS <-> Python）
"""
import os
import sys
import time
import base64
import shutil
import threading

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtWebChannel import QWebChannel

import config
import autostart
from clipboard_sender import copy_to_clipboard, paste_and_send
from clipboard_history import ClipboardHistory


def _resource_dir():
    """资源目录：打包后在 _MEIPASS，开发时在脚本目录。"""
    if getattr(sys, "frozen", False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


UI_DIR = os.path.join(_resource_dir(), "ui")
INDEX_HTML = os.path.join(UI_DIR, "index.html")


def image_to_data_url(path, size=96):
    """把图片转成 data URL（供前端 <img> 展示）。"""
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


def build_meme_list():
    """构造表情列表数据，供前端渲染。"""
    result = []
    for path in config.list_memes():
        name = os.path.basename(path)
        stem, ext = os.path.splitext(name)
        try:
            size_kb = os.path.getsize(path) / 1024
            meta = f"{ext.lstrip('.').upper()} · {size_kb:.0f} KB"
        except OSError:
            meta = ext.lstrip(".").upper()
        result.append({
            "path": path,
            "name": stem,
            "meta": meta,
            "dataUrl": image_to_data_url(path),
        })
    return result


class Bridge(QtCore.QObject):
    """JS <-> Python 通信桥。"""

    memesLoaded = QtCore.pyqtSignal(list)
    historyLoaded = QtCore.pyqtSignal(list)
    dataDirLoaded = QtCore.pyqtSignal(str)
    settingsLoaded = QtCore.pyqtSignal(dict)

    def __init__(self, window, history):
        super().__init__()
        self.window = window
        self.history = history

    @QtCore.pyqtSlot()
    def refresh(self):
        """前端请求刷新数据。"""
        self.memesLoaded.emit(build_meme_list())

    @QtCore.pyqtSlot(str)
    def copyMeme(self, path):
        """复制表情到剪贴板。"""
        ok = copy_to_clipboard(path)
        if ok and config.load_config().get("auto_hide_on_click", True):
            QtCore.QTimer.singleShot(350, self.window.hide)

    @QtCore.pyqtSlot(str)
    def deleteMeme(self, path):
        """删除表情。"""
        try:
            os.remove(path)
        except OSError:
            pass
        self.refresh()

    @QtCore.pyqtSlot()
    def importFromFolder(self):
        """从文件夹导入。"""
        files, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self.window, "选择表情包图片", "",
            "图片文件 (*.png *.jpg *.jpeg *.gif *.bmp *.webp);;所有文件 (*.*)")
        if files:
            self._import_files(files)

    @QtCore.pyqtSlot()
    def importFromClipboard(self):
        """从剪贴板导入。"""
        try:
            clipboard = QtWidgets.QApplication.clipboard()
            mime = clipboard.mimeData()
            if mime.hasImage():
                img = clipboard.image()
                timestamp = int(time.time() * 1000)
                dest = os.path.join(config.MEME_DIR, f"meme_{timestamp}.png")
                img.save(dest, "PNG")
                self.refresh()
                self.window.notify("导入成功")
            else:
                QtWidgets.QMessageBox.information(
                    self.window, "提示", "剪贴板中没有图片，请先在别处复制一张图片")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self.window, "错误", f"粘贴导入失败：{e}")

    @QtCore.pyqtSlot()
    def minimize(self):
        self.window.showMinimized()

    @QtCore.pyqtSlot()
    def hideWindow(self):
        self.window.hide()

    # ---------- 剪贴板历史 ----------
    @QtCore.pyqtSlot()
    def getHistory(self):
        """前端请求剪贴板历史。"""
        self.historyLoaded.emit(self.history.get_items())

    @QtCore.pyqtSlot(str)
    def copyHistoryItem(self, item_id):
        """把历史项复制回剪贴板。"""
        item = self.history.find(item_id)
        if not item:
            return
        if item["type"] == "text":
            QtWidgets.QApplication.clipboard().setText(item["content"])
        else:
            copy_to_clipboard(item["file"])
        # 复制历史项时也更新监听器的去重 hash，避免重复记录
        self.history._last_hash = item.get("hash")
        self.window.notify("已复制")

    @QtCore.pyqtSlot(str)
    def deleteHistoryItem(self, item_id):
        self.history.delete(item_id)
        self.getHistory()

    @QtCore.pyqtSlot(str)
    def pinHistoryItem(self, item_id):
        self.history.toggle_pin(item_id)
        self.getHistory()

    @QtCore.pyqtSlot()
    def clearHistory(self):
        self.history.clear()
        self.getHistory()
        self.window.notify("已清空历史")

    # ---------- 存储目录 ----------
    @QtCore.pyqtSlot()
    def getDataDir(self):
        self.dataDirLoaded.emit(config.BASE_DIR)

    @QtCore.pyqtSlot()
    def chooseDataDir(self):
        """弹目录选择框，自定义存储位置。"""
        new_dir = QtWidgets.QFileDialog.getExistingDirectory(
            self.window, "选择数据存储目录", config.BASE_DIR)
        if new_dir and config.set_data_dir(new_dir):
            config.ensure_dirs()
            self.dataDirLoaded.emit(config.BASE_DIR)
            self.refresh()
            self.getHistory()
            self.getSettings()
            self.window.notify("存储目录已更改")
        elif new_dir:
            self.window.notify("目录设置失败")

    # ---------- 设置 ----------
    @QtCore.pyqtSlot()
    def getSettings(self):
        """返回完整设置项。"""
        cfg = config.load_config()
        self.settingsLoaded.emit({
            "data_dir": config.BASE_DIR,
            "autostart": autostart.is_autostart_enabled(),
            "watch_clipboard": cfg.get("watch_clipboard", True),
            "send_hotkey": cfg.get("send_hotkey", "ctrl+shift+v"),
            "auto_hide_on_click": cfg.get("auto_hide_on_click", True),
        })

    @QtCore.pyqtSlot(bool)
    def setAutostart(self, enabled):
        ok = autostart.set_autostart(enabled)
        if not ok:
            self.window.notify("开机自启设置失败")
        self.getSettings()

    @QtCore.pyqtSlot(bool)
    def setWatchClipboard(self, enabled):
        cfg = config.load_config()
        cfg["watch_clipboard"] = enabled
        config.save_config(cfg)
        self.getSettings()

    @QtCore.pyqtSlot(bool)
    def setAutoHide(self, enabled):
        cfg = config.load_config()
        cfg["auto_hide_on_click"] = enabled
        config.save_config(cfg)
        self.getSettings()

    def _import_files(self, files):
        config.ensure_dirs()
        imported = 0
        for f in files:
            if not f.lower().endswith(config.IMAGE_EXTS):
                continue
            base = os.path.basename(f)
            dest = os.path.join(config.MEME_DIR, base)
            if os.path.exists(dest):
                stem, ext = os.path.splitext(base)
                dest = os.path.join(config.MEME_DIR,
                                    f"{stem}_{int(time.time()*1000)}{ext}")
            try:
                shutil.copy2(f, dest)
                imported += 1
            except OSError:
                pass
        self.refresh()
        self.window.notify(f"已导入 {imported} 个表情")


class MainWindow(QtWidgets.QWidget):
    """主窗口：无边框 + QWebEngineView 壳。"""

    def __init__(self, history):
        super().__init__()
        self.history = history
        self.cfg = config.load_config()
        self.setWindowTitle(config.APP_NAME)
        self.setWindowFlags(
            QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint)
        # 透明背景，让 HTML 的圆角/毛玻璃生效
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)

        self._build_ui()
        self._center()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # Web 引擎视图
        self.webview = QWebEngineView()
        self.webview.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        self.webview.page().setBackgroundColor(QtCore.Qt.transparent)

        # 桥接
        self.channel = QWebChannel()
        self.bridge = Bridge(self, self.history)
        self.channel.registerObject("bridge", self.bridge)
        self.webview.page().setWebChannel(self.channel)

        # 加载本地 HTML
        url = QtCore.QUrl.fromLocalFile(INDEX_HTML)
        self.webview.load(url)

        layout.addWidget(self.webview)

    def _center(self):
        self.resize(880, 620)
        self.setMinimumSize(560, 440)
        screen = QtWidgets.QApplication.primaryScreen().availableGeometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)

    # ===== 无边框窗口自由缩放（8向边缘拖拽）=====
    RESIZE_MARGIN = 6

    def nativeEvent(self, eventType, message):
        """用原生 Windows 消息实现边缘缩放（WPARAM/LPARAM）。"""
        try:
            import ctypes
            from ctypes import wintypes
        except ImportError:
            return super().nativeEvent(eventType, message)

        if eventType == b"windows_generic_MSG" or eventType == "windows_generic_MSG":
            msg = ctypes.cast(int(message), ctypes.POINTER(wintypes.MSG)).contents
            WM_NCHITTEST = 0x0084
            if msg.message == WM_NCHITTEST:
                x = ctypes.c_short(msg.lParam & 0xFFFF).value
                y = ctypes.c_short(msg.lParam >> 16).value
                gx, gy = self.mapFromGlobal(QtCore.QPoint(x, y)).x(), \
                         self.mapFromGlobal(QtCore.QPoint(x, y)).y()
                w, h = self.width(), self.height()
                m = self.RESIZE_MARGIN
                left = gx < m
                right = gx > w - m
                top = gy < m
                bottom = gy > h - m
                # HT 常量
                HTLEFT, HTRIGHT, HTTOP, HTBOTTOM = 10, 11, 12, 15
                HTTOPLEFT, HTTOPRIGHT, HTBOTTOMLEFT, HTBOTTOMRIGHT = 13, 14, 16, 17
                HTCLIENT = 1
                HTCAPTION = 2
                # 窗口外圈留了 10px 阴影边距，命中测试要先扣掉
                PAD = 10
                ix, iy = gx - PAD, gy - PAD
                if top and left:
                    return True, HTTOPLEFT
                if top and right:
                    return True, HTTOPRIGHT
                if bottom and left:
                    return True, HTBOTTOMLEFT
                if bottom and right:
                    return True, HTBOTTOMRIGHT
                if left:
                    return True, HTLEFT
                if right:
                    return True, HTRIGHT
                if top:
                    return True, HTTOP
                if bottom:
                    return True, HTBOTTOM
                # 仅最顶部品牌栏（内容坐标 < 46px）可拖动，
                # 右侧 100px 留给最小化/关闭按钮，不参与拖动
                if PAD <= iy < PAD + 46 and ix < w - PAD - 100:
                    return True, HTCAPTION
                return True, HTCLIENT
        return super().nativeEvent(eventType, message)

    def notify(self, text):
        """通知前端显示 toast。"""
        js = f"showToast({json_dumps(text)});"
        self.webview.page().runJavaScript(js)

    def refresh(self):
        self.bridge.refresh()

    # 无边框窗口拖拽：由 HTML 标题栏的 -webkit-app-region 处理，
    # 但 Qt 无边框窗口需要额外处理，这里通过 JS 回调拖拽坐标
    def show_and_refresh(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()
        self.refresh()


def json_dumps(s):
    import json
    return json.dumps(s, ensure_ascii=False)


class TrayIcon(QtWidgets.QSystemTrayIcon):
    """系统托盘图标。"""

    def __init__(self, window, parent=None):
        super().__init__(self._make_icon(), parent)
        self.window = window
        self.setToolTip(config.APP_NAME)

        menu = QtWidgets.QMenu()
        show_action = menu.addAction("打开表情助手")
        show_action.triggered.connect(self.show_window)
        import_action = menu.addAction("导入表情包")
        import_action.triggered.connect(self.import_memes)
        menu.addSeparator()
        # 开机自启开关
        self.autostart_action = menu.addAction("开机自启")
        self.autostart_action.setCheckable(True)
        self.autostart_action.setChecked(autostart.is_autostart_enabled())
        self.autostart_action.triggered.connect(self._toggle_autostart)
        menu.addSeparator()
        quit_action = menu.addAction("退出")
        quit_action.triggered.connect(QtWidgets.QApplication.quit)

        self.setContextMenu(menu)
        self.activated.connect(self._on_activated)

    def _make_icon(self):
        pixmap = QtGui.QPixmap(64, 64)
        pixmap.fill(QtCore.Qt.transparent)
        p = QtGui.QPainter(pixmap)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        p.setBrush(QtGui.QColor("#0067C0"))
        p.setPen(QtCore.Qt.NoPen)
        p.drawEllipse(2, 2, 60, 60)
        p.setBrush(QtGui.QColor("white"))
        p.drawEllipse(18, 24, 10, 10)
        p.drawEllipse(36, 24, 10, 10)
        pen = QtGui.QPen(QtGui.QColor("white"))
        pen.setWidth(3)
        p.setPen(pen)
        p.drawArc(22, 34, 20, 14, 0 * 16, 180 * 16)
        p.end()
        return QtGui.QIcon(pixmap)

    def _on_activated(self, reason):
        # 单击或双击托盘图标都呼出窗口
        if reason in (QtWidgets.QSystemTrayIcon.Trigger,
                      QtWidgets.QSystemTrayIcon.DoubleClick):
            self.show_window()

    def show_window(self):
        self.window.show_and_refresh()

    def import_memes(self):
        self.show_window()
        self.window.bridge.importFromFolder()

    def _toggle_autostart(self, checked):
        ok = autostart.set_autostart(checked)
        if not ok:
            self.autostart_action.setChecked(not checked)
            self.window.notify("开机自启设置失败")


class HotkeyManager:
    """全局热键。"""

    def __init__(self, hotkey):
        self.hotkey = hotkey
        self._thread = None

    def start(self):
        def worker():
            try:
                import keyboard
                keyboard.add_hotkey(self.hotkey, self._handler)
                keyboard.wait()
            except Exception:
                pass

        self._thread = threading.Thread(target=worker, daemon=True)
        self._thread.start()

    def _handler(self):
        paste_and_send()


class ClipboardWatcher(QtCore.QObject):
    """剪贴板监听器：定时轮询系统剪贴板，有变化就记录到历史。"""

    new_item = QtCore.pyqtSignal()

    def __init__(self, history, parent=None):
        super().__init__(parent)
        self.history = history
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._check)
        self._timer.start(600)  # 600ms 轮询

    def _check(self):
        if not config.load_config().get("watch_clipboard", True):
            return
        clipboard = QtWidgets.QApplication.clipboard()
        mime = clipboard.mimeData()
        try:
            if mime.hasImage():
                img = clipboard.image()
                if not img.isNull() and self.history.add_image(img):
                    self.new_item.emit()
            elif mime.hasText():
                text = clipboard.text()
                if text and self.history.add_text(text):
                    self.new_item.emit()
        except Exception:
            pass


def main():
    config.ensure_dirs()
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)

    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName(config.APP_NAME)
    app.setQuitOnLastWindowClosed(False)

    history = ClipboardHistory()
    window = MainWindow(history)
    tray = TrayIcon(window)
    tray.show()

    # 剪贴板监听：有新记录时静默刷新（窗口可见才刷新前端，省资源）
    watcher = ClipboardWatcher(history, parent=app)
    def on_new_item():
        if window.isVisible():
            window.bridge.getHistory()
    watcher.new_item.connect(on_new_item)

    hotkey = config.load_config().get("send_hotkey", "ctrl+shift+v")
    HotkeyManager(hotkey).start()

    # 开机自启时只驻留托盘，不弹窗；手动启动则弹窗
    if "--tray" in sys.argv:
        window.hide()
    else:
        window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()

"""剪贴板发送模块：负责把图片复制到剪贴板，以及模拟 Ctrl+V + Enter 发送。"""
import time
import pyperclip
import keyboard


def copy_image_to_clipboard(image_path):
    """把图片复制到 Windows 剪贴板（CF_DIB 格式，QQ 可直接粘贴）。

    GIF 动图会把整个文件以 CF_HDROP + CF_BITMAP 形式处理，
    这里对 GIF 走文件拖拽复制，保留动画；静态图走 DIB。
    """
    import win32clipboard
    from PIL import Image
    import io

    lower = image_path.lower()
    if lower.endswith(".gif"):
        # GIF 动图：以文件列表方式复制，QQ 能识别为图片文件
        win32clipboard.OpenClipboard()
        try:
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(
                win32clipboard.CF_HDROP, (image_path,))
        finally:
            win32clipboard.CloseClipboard()
        return True

    img = Image.open(image_path)
    # 转为 RGB，避免 PNG 透明通道导致粘贴异常
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGB")

    output = io.BytesIO()
    # 用 BMP 格式写入内存（剪贴板 DIB 本质是 BMP）
    img.convert("RGB").save(output, "BMP")
    data = output.getvalue()[14:]  # 去掉 BMP 文件头，保留 DIB 数据

    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
    finally:
        win32clipboard.CloseClipboard()
    return True


def copy_image_fallback(image_path):
    """备用方案：用 pyperclip 复制文件路径（某些环境下的兜底）。"""
    pyperclip.copy(image_path)
    return True


def copy_to_clipboard(image_path):
    """复制图片到剪贴板，优先用 CF_DIB 方案，失败则回退。"""
    try:
        copy_image_to_clipboard(image_path)
        return True
    except Exception:
        try:
            copy_image_fallback(image_path)
            return True
        except Exception:
            return False


def paste_and_send():
    """模拟 Ctrl+V（粘贴）然后 Enter（发送）。"""
    try:
        # 等待剪贴板就绪
        time.sleep(0.1)
        keyboard.send("ctrl+v")
        time.sleep(0.15)
        keyboard.send("enter")
        return True
    except Exception:
        return False

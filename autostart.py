"""开机自启管理：读写 Windows 注册表 Run 项。"""
import os
import sys

try:
    import winreg
    _HAS_WINREG = True
except ImportError:
    _HAS_WINREG = False

APP_NAME = "QQMemeTray"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def _exe_path():
    """返回开机自启启动命令（带 --tray 参数，启动只驻留托盘）。"""
    if getattr(sys, "frozen", False):
        # PyInstaller 打包后：直接用 exe 路径
        return f'"{sys.executable}" --tray'
    # 开发环境：pythonw + main.py --tray
    main_py = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py")
    pythonw = sys.executable.replace("python.exe", "pythonw.exe")
    return f'"{pythonw}" "{main_py}" --tray'


def set_autostart(enable=True):
    """开启/关闭开机自启。返回是否成功。"""
    if not _HAS_WINREG:
        return False
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE)
        if enable:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, _exe_path())
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
        return True
    except OSError:
        return False


def is_autostart_enabled():
    """查询是否已开启开机自启。"""
    if not _HAS_WINREG:
        return False
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ)
        try:
            winreg.QueryValueEx(key, APP_NAME)
            winreg.CloseKey(key)
            return True
        except FileNotFoundError:
            winreg.CloseKey(key)
            return False
    except OSError:
        return False

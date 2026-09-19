"""Windows 平台绑定:pywin32 / MSS / PyAutoGUI / keyboard(W5)。

本模块把 W3 定义的四个基础接口接到真实 Windows API,
**只能在 Windows 上导入使用**(实例化时才 import win32/mss/pyautogui/keyboard);
跨平台组合逻辑见 game/windows_adapter.py,用 Mock 即可在 macOS 测试。

延迟导入约定:每个类在首次实例化时才 import 对应库,
让"未安装依赖"的错误推迟到真正使用时,并给出中文提示。
"""

from __future__ import annotations

from collections.abc import Callable

from game.input import HotkeyManager, InputController
from game.screen import ScreenCapture, ScreenImage
from game.window import WindowInfo, WindowManager
from utils.logger import get_logger

logger = get_logger("game.win")

_IS_WINDOWS_HINT = (
    "本模块仅支持 Windows,且需要安装游戏自动化依赖组: "
    "pip install -e .[windows] 或 pip install pywin32 mss pyautogui keyboard"
)


def _import_win32gui():
    try:
        import win32gui
    except ImportError as exc:
        raise RuntimeError(f"无法导入 pywin32: {exc};{_IS_WINDOWS_HINT}") from exc
    return win32gui


def _import_mss():
    try:
        import mss
    except ImportError as exc:
        raise RuntimeError(f"无法导入 mss: {exc};{_IS_WINDOWS_HINT}") from exc
    return mss


def _import_pyautogui():
    try:
        import pyautogui
    except ImportError as exc:
        raise RuntimeError(f"无法导入 pyautogui: {exc};{_IS_WINDOWS_HINT}") from exc
    return pyautogui


def _import_keyboard():
    try:
        import keyboard
    except ImportError as exc:
        raise RuntimeError(f"无法导入 keyboard: {exc};{_IS_WINDOWS_HINT}") from exc
    return keyboard


def _screen_image(width: int, height: int, rgb_bytes: bytes) -> ScreenImage:
    """由 RGB 字节流构造 ScreenImage(长度不符时给出明确错误)。"""
    expected = width * height * 3
    if len(rgb_bytes) != expected:
        raise ValueError(
            f"截图数据长度 {len(rgb_bytes)} 与尺寸不匹配,期望 {expected}"
            f"(width={width}, height={height})"
        )
    return ScreenImage(width, height, "RGB", rgb_bytes)


class Win32WindowManager(WindowManager):
    """基于 win32gui 的窗口查找与激活。"""

    def __init__(self) -> None:
        self._win32gui = _import_win32gui()

    def find(self, title_contains: str) -> WindowInfo | None:
        win32gui = self._win32gui
        result: WindowInfo | None = None

        def _enum(handle: int, _unused) -> None:
            nonlocal result
            if result is not None:
                return
            if not win32gui.IsWindowVisible(handle):
                return
            title = win32gui.GetWindowText(handle)
            if title_contains in title:
                left, top, right, bottom = win32gui.GetWindowRect(handle)
                result = WindowInfo(
                    handle=handle,
                    title=title,
                    left=left,
                    top=top,
                    width=max(1, right - left),
                    height=max(1, bottom - top),
                )

        win32gui.EnumWindows(_enum, None)
        return result

    def activate(self, window: WindowInfo) -> None:
        win32gui = self._win32gui
        win32gui.ShowWindow(window.handle, win32gui.SW_RESTORE)
        win32gui.SetForegroundWindow(window.handle)

    def is_alive(self, window: WindowInfo) -> bool:
        return bool(self._win32gui.IsWindow(window.handle))


class MssScreenCapture(ScreenCapture):
    """基于 MSS 的屏幕截图(BGRA 原生输出 → 转 RGB)。"""

    def __init__(self) -> None:
        self._mss = _import_mss()

    def capture_region(self, left: int, top: int, width: int, height: int) -> ScreenImage:
        with self._mss.mss() as sct:
            raw = sct.grab({"left": left, "top": top, "width": width, "height": height})
        # BGRA → RGB(去掉 alpha,反转通道顺序)
        bgra = bytes(raw)
        rgb = bytearray(len(bgra) // 4 * 3)
        rgb[0::3] = bgra[2::4]
        rgb[1::3] = bgra[1::4]
        rgb[2::3] = bgra[0::4]
        return _screen_image(width, height, bytes(rgb))

    def capture_window(self, window: WindowInfo) -> ScreenImage:
        return self.capture_region(window.left, window.top, window.width, window.height)


class PyAutoGuiInput(InputController):
    """基于 PyAutoGUI 的鼠标键盘输入。"""

    def __init__(self) -> None:
        pyautogui = _import_pyautogui()
        pyautogui.FAILSAFE = True  # 鼠标甩到左上角可紧急中止(DESIGN 17 的额外保险)
        pyautogui.PAUSE = 0.05
        self._pyautogui = pyautogui

    def click(self, x: int, y: int) -> None:
        self._pyautogui.click(x, y)

    def press_key(self, key: str) -> None:
        self._pyautogui.press(key)


class KeyboardHotkeyManager(HotkeyManager):
    """基于 keyboard 库的全局热键(W3 接口的 Windows 实现)。"""

    def __init__(self) -> None:
        self._keyboard = _import_keyboard()
        self._hooks: dict[str, Callable[[], None]] = {}

    def register(self, key: str, callback: Callable[[], None]) -> None:
        if key in self._hooks:
            self.unregister(key)
        self._keyboard.add_hotkey(key, callback)
        self._hooks[key] = callback
        logger.info("已注册全局热键 %s", key)

    def unregister(self, key: str) -> None:
        """注销单个热键;未注册时静默忽略。"""
        if key in self._hooks:
            self._keyboard.remove_hotkey(self._hooks.pop(key))

    def unregister_all(self) -> None:
        for key in list(self._hooks):
            self.unregister(key)

"""windows_bindings 平台绑定测试(W5)。

macOS 上无法实例化真实绑定(依赖 win32/mss/pyautogui/keyboard),
只验证:
1. 模块本身可导入(延迟导入设计,顶层无 Windows 依赖)
2. 实例化时因缺少 Windows 库而报 RuntimeError 且提示中文安装信息
3. _screen_image 辅助函数的长度校验(纯逻辑,可跨平台测)
"""

from __future__ import annotations

import pytest

import game.windows_bindings as wb


class TestDelayedImport:
    """延迟导入:模块可导入,实例化给出中文错误提示。"""

    def test_module_importable_without_windows(self):
        # 顶层导入不触发任何 win32/mss/pyautogui/keyboard 导入
        assert callable(wb.Win32WindowManager)
        assert callable(wb.MssScreenCapture)
        assert callable(wb.PyAutoGuiInput)
        assert callable(wb.KeyboardHotkeyManager)

    @pytest.mark.parametrize(
        ("cls", "lib_label"),
        [
            (wb.Win32WindowManager, "pywin32"),
            (wb.MssScreenCapture, "mss"),
            (wb.PyAutoGuiInput, "pyautogui"),
            (wb.KeyboardHotkeyManager, "keyboard"),
        ],
    )
    def test_instantiation_requires_windows_libs(self, cls, lib_label):
        """macOS 上缺库 → RuntimeError,消息包含库名与安装提示。"""
        with pytest.raises(RuntimeError, match=lib_label):
            cls()

    def test_error_message_contains_install_hint(self):
        with pytest.raises(RuntimeError, match=r"pip install"):
            wb.Win32WindowManager()


class TestScreenImageHelper:
    def test_valid_rgb_bytes(self):
        image = wb._screen_image(4, 3, b"\x01" * (4 * 3 * 3))
        assert (image.width, image.height, image.mode) == (4, 3, "RGB")
        assert len(image.data) == 4 * 3 * 3

    def test_length_mismatch_raises(self):
        with pytest.raises(ValueError, match="不匹配"):
            wb._screen_image(4, 3, b"\x01" * 10)

"""截图接口(W3 基础能力)。

对应 DESIGN.md 21 节 W3:截取窗口。
本文件只定义接口、轻量图像容器与测试用 Mock;
真实实现(MSS)在 W5 阶段提供,需要 Windows 环境。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from game.window import WindowInfo

#: 像素格式 → 每像素字节数(BGRA 为 MSS 的原生输出格式)
IMAGE_CHANNELS: dict[str, int] = {"L": 1, "RGB": 3, "BGR": 3, "RGBA": 4, "BGRA": 4}


@dataclass(frozen=True)
class ScreenImage:
    """轻量图像容器。

    W4 引入 OpenCV 之前,截图统一用本结构传递;
    ``data`` 按 ``mode`` 的通道顺序逐像素排列。
    """

    width: int
    height: int
    mode: str = "RGB"
    data: bytes = b""

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError(f"图像尺寸必须为正,得到 {self.width}x{self.height}")
        channels = IMAGE_CHANNELS.get(self.mode)
        if channels is None:
            raise ValueError(
                f"不支持的像素格式 {self.mode!r},可选 {sorted(IMAGE_CHANNELS)}"
            )
        expected = self.width * self.height * channels
        if len(self.data) != expected:
            raise ValueError(
                f"像素数据长度 {len(self.data)} 与尺寸不匹配,"
                f"期望 {expected}(width={self.width}, height={self.height}, mode={self.mode})"
            )

    @property
    def channels(self) -> int:
        """每像素字节数。"""
        return IMAGE_CHANNELS[self.mode]


def solid_image(
    width: int,
    height: int,
    color: tuple[int, ...] = (0, 0, 0),
    mode: str = "RGB",
) -> ScreenImage:
    """生成纯色图像(测试与 Mock 用)。"""
    channels = IMAGE_CHANNELS[mode]
    if len(color) != channels:
        raise ValueError(f"颜色通道数 {len(color)} 与格式 {mode} 不匹配")
    return ScreenImage(width, height, mode, bytes(color) * (width * height))


def crop(
    image: ScreenImage, x: int, y: int, width: int, height: int
) -> ScreenImage:
    """裁剪图像区域(纯字节操作,不依赖 numpy)。

    Args:
        image: 原图像。
        x, y: 区域左上角坐标。
        width, height: 区域宽高。

    Raises:
        ValueError: 区域尺寸非法或越界。
    """
    if width <= 0 or height <= 0:
        raise ValueError(f"裁剪尺寸必须为正,得到 {width}x{height}")
    if x < 0 or y < 0 or x + width > image.width or y + height > image.height:
        raise ValueError(
            f"裁剪区域越界: ({x}, {y}, {width}, {height}),"
            f"图像尺寸 {image.width}x{image.height}"
        )
    channels = image.channels
    row_bytes = image.width * channels
    rows = []
    for row in range(y, y + height):
        start = row * row_bytes + x * channels
        rows.append(image.data[start : start + width * channels])
    return ScreenImage(width, height, image.mode, b"".join(rows))


class ScreenCapture(ABC):
    """截图接口。"""

    @abstractmethod
    def capture_window(self, window: WindowInfo) -> ScreenImage:
        """截取整个窗口。"""

    @abstractmethod
    def capture_region(self, left: int, top: int, width: int, height: int) -> ScreenImage:
        """截取屏幕区域(W4 的 ROI 截图入口)。"""


class MockScreenCapture(ScreenCapture):
    """测试用 Mock:返回可编程的纯色图像。"""

    def __init__(self, fill_color: tuple[int, ...] = (0, 0, 0)) -> None:
        self.fill_color = fill_color
        self.window_images: dict[int, ScreenImage] = {}
        self.region_image: ScreenImage | None = None
        self.calls: list[tuple[str, tuple]] = []

    # -- 场景编排 --

    def set_window_image(self, handle: int, image: ScreenImage) -> None:
        """为指定窗口预编程截图;未编程的窗口返回纯色图。"""
        self.window_images[handle] = image

    def set_region_image(self, image: ScreenImage) -> None:
        """为所有区域截图预编程返回值;缺省按区域尺寸生成纯色图。"""
        self.region_image = image

    # -- 断言辅助 --

    def called(self, name: str) -> int:
        """某接口方法被调用的次数。"""
        return sum(1 for call_name, _ in self.calls if call_name == name)

    # -- ScreenCapture 接口实现 --

    def capture_window(self, window: WindowInfo) -> ScreenImage:
        self.calls.append(("capture_window", (window.handle,)))
        return self.window_images.get(
            window.handle,
            solid_image(window.width, window.height, self.fill_color),
        )

    def capture_region(self, left: int, top: int, width: int, height: int) -> ScreenImage:
        self.calls.append(("capture_region", (left, top, width, height)))
        return self.region_image or solid_image(width, height, self.fill_color)

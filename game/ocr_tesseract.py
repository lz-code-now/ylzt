"""TesseractOcrEngine:OCR 真实引擎(W6)。

对应 DESIGN.md 第 3 节与 21 节 W6:接入真实 OCR 引擎。
基于 pytesseract(Pillow 桥接)+ 本机 Tesseract 可执行文件,
跨平台可用(macOS 上即可开发验证,Windows 上装 Tesseract 后同样工作)。

识别流程:
1. ScreenImage(RGB)→ numpy → 灰度
2. 预处理:3 倍放大 → OTSU 二值化 → 反色(游戏 UI 浅字深底时提高对比)
3. pytesseract.image_to_data 获取逐词文本与置信度
4. 拼接文本;平均置信度低于 min_confidence 时判失败

依赖:本机安装 Tesseract 可执行文件(Windows 安装后需在
config/settings.yaml 的 game.ocr.tesseract_cmd 指定路径)。
未安装或调用失败时返回失败 RecognitionResult,不抛异常,
与 W4 的"识别失败走 debug 截图 + 状态机恢复链路"策略一致。
"""

from __future__ import annotations

import numpy as np
import pytesseract

from game.ocr import OcrEngine
from game.screen import ScreenImage
from models.recognition import RecognitionResult
from models.settings import OcrSection
from utils.logger import get_logger

logger = get_logger("game.ocr")

# 玩家可感知的失败原因标签
_TESSERACT_NOT_FOUND = "Tesseract 不可用(未安装或路径错误)"


class TesseractOcrEngine(OcrEngine):
    """基于 Tesseract 的 OCR 引擎实现。

    Args:
        config: game.ocr 配置(引擎路径/语言/PSM/置信度阈值)。
    """

    def __init__(self, config: OcrSection | None = None) -> None:
        self.config = config or OcrSection(engine="tesseract")
        if self.config.tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = self.config.tesseract_cmd

    def recognize(self, image: ScreenImage) -> RecognitionResult:
        """识别图像文本;任何引擎级失败都转为失败结果。"""
        try:
            pil_image = self._preprocess(image)
            data = pytesseract.image_to_data(
                pil_image,
                lang=self.config.lang,
                config=f"--psm {self.config.psm}",
                output_type=pytesseract.Output.DICT,
            )
        except pytesseract.TesseractNotFoundError:
            logger.error("%s: 请安装 Tesseract 或检查 game.ocr.tesseract_cmd", _TESSERACT_NOT_FOUND)
            return RecognitionResult(success=False, detail=_TESSERACT_NOT_FOUND)
        except Exception as exc:  # OCR 引擎级错误不应中断挂机循环
            logger.warning("OCR 调用失败: %s", exc)
            return RecognitionResult(success=False, detail=f"OCR 调用失败: {exc}")

        words: list[str] = []
        confidences: list[float] = []
        for text, conf in zip(data["text"], data["conf"]):
            text = text.strip()
            if not text:
                continue
            words.append(text)
            try:
                confidences.append(float(conf))
            except (TypeError, ValueError):
                continue

        if not words:
            return RecognitionResult(success=False, detail="OCR 未识别到文本")

        text = " ".join(words)
        confidence = sum(confidences) / len(confidences) / 100.0
        if confidence < self.config.min_confidence / 100.0:
            return RecognitionResult(
                success=False,
                value=text,
                confidence=confidence,
                detail=f"OCR 置信度 {confidence:.2f} 低于阈值 {self.config.min_confidence / 100.0:.2f}",
            )
        return RecognitionResult(success=True, value=text, confidence=confidence)

    def _preprocess(self, image: ScreenImage):
        """灰度 → 放大 → OTSU 二值化 → 反色,返回 Pillow 图像。"""
        from PIL import Image

        channels = 3 if image.mode == "RGB" else 4
        array = np.frombuffer(image.data, dtype=np.uint8).reshape(
            image.height, image.width, channels
        )[:, :, :3]
        gray = array[:, :, 0] * 0.299 + array[:, :, 1] * 0.587 + array[:, :, 2] * 0.114
        gray = gray.astype(np.uint8)
        # 游戏小字号文本放大 3 倍,显著提升识别率
        scale = 3
        resized = np.kron(gray, np.ones((scale, scale), dtype=np.uint8))
        # OTSU 全局阈值(numpy 实现,避免额外依赖 cv2 阈值语义差异)
        threshold = _otsu_threshold(resized)
        binary = np.where(resized > threshold, 255, 0).astype(np.uint8)
        # 游戏常见浅色文字/深色背景 → 反色为黑字白底(Tesseract 友好)
        if binary.mean() < 128:
            binary = 255 - binary
        return Image.fromarray(binary, mode="L")


def _otsu_threshold(gray: np.ndarray) -> int:
    """OTSU 大津法求二值化阈值(纯 numpy,64 段直方图近似)。"""
    hist, _ = np.histogram(gray, bins=256, range=(0, 256))
    total = gray.size
    sum_total = np.dot(np.arange(256), hist)
    sum_b = 0.0
    weight_b = 0.0
    best_threshold = 127
    best_variance = -1.0
    for t in range(256):
        weight_b += hist[t]
        if weight_b == 0:
            continue
        weight_f = total - weight_b
        if weight_f == 0:
            break
        sum_b += t * hist[t]
        mean_b = sum_b / weight_b
        mean_f = (sum_total - sum_b) / weight_f
        variance = weight_b * weight_f * (mean_b - mean_f) ** 2
        if variance > best_variance:
            best_variance = variance
            best_threshold = t
    return best_threshold

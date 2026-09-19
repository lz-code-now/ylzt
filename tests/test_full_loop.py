"""W6 测试:真实挂机闭环。

- TesseractOcrEngine:预处理 + 真实 tesseract 识别(环境可用时)+
  引擎级失败容错(找不到可执行文件不抛异常)
- OcrSection 配置校验
- RuntimeRunner:组装、热键注册、紧急停止、mock 闭环全链路
  (挂机 → 死亡×6 → 5 次原地复活 → 安全复活 → 回城 → 再挂机)
"""

from __future__ import annotations

import shutil

import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFont

from app.runner import RuntimeRunner, RunnerError
from game.input import MockHotkeyManager
from game.mock_adapter import MockGameAdapter
from game.ocr import MockOcrEngine
from game.ocr_tesseract import TesseractOcrEngine, _otsu_threshold
from game.screen import ScreenImage, solid_image
from models.settings import AppSettings, OcrSection
from utils.validation import ConfigValidationError

TESSERACT_AVAILABLE = shutil.which("tesseract") is not None
# macOS 中文字体(仅用于合成文本图)
FONT_CANDIDATES = [
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
]


def text_image(text: str, width: int = 300, height: int = 60) -> ScreenImage:
    """合成黑字白底文本图(模拟游戏 UI 文本)。"""
    font = None
    for candidate in FONT_CANDIDATES:
        try:
            font = ImageFont.truetype(candidate, 36)
            break
        except OSError:
            continue
    if font is None:
        font = ImageFont.load_default()
    img = Image.new("L", (width, height), color=255)
    ImageDraw.Draw(img).text((10, 10), text, fill=0, font=font)
    array = np.array(img)
    rgb = np.stack([array] * 3, axis=2).astype(np.uint8)
    return ScreenImage(width, height, "RGB", rgb.tobytes())


# ----------------------------------------------------------------------
# OcrSection 配置
# ----------------------------------------------------------------------


class TestOcrSection:
    def test_defaults(self):
        ocr = AppSettings.from_dict({}).game.ocr
        assert ocr.engine == "mock"
        assert ocr.tesseract_cmd is None
        assert ocr.lang == "chi_sim+eng"
        assert ocr.psm == 7
        assert ocr.min_confidence == 60.0

    def test_full_config(self):
        settings = AppSettings.from_dict(
            {
                "game": {
                    "ocr": {
                        "engine": "tesseract",
                        "tesseract_cmd": "/usr/local/bin/tesseract",
                        "lang": "chi_sim",
                        "psm": 6,
                        "min_confidence": 70,
                    }
                }
            }
        )
        ocr = settings.game.ocr
        assert ocr.engine == "tesseract"
        assert ocr.tesseract_cmd == "/usr/local/bin/tesseract"
        assert ocr.lang == "chi_sim"
        assert ocr.psm == 6
        assert ocr.min_confidence == 70.0

    def test_invalid_engine(self):
        with pytest.raises(ConfigValidationError, match="engine"):
            AppSettings.from_dict({"game": {"ocr": {"engine": "baidu"}}})

    def test_negative_min_confidence(self):
        with pytest.raises(ConfigValidationError, match="min_confidence"):
            AppSettings.from_dict({"game": {"ocr": {"min_confidence": -1}}})

    def test_unknown_key(self):
        with pytest.raises(ConfigValidationError, match="未知字段"):
            AppSettings.from_dict({"game": {"ocr": {"nope": 1}}})


# ----------------------------------------------------------------------
# TesseractOcrEngine
# ----------------------------------------------------------------------


class TestTesseractOcrEngine:
    def test_otsu_threshold_bimodal(self):
        """双峰直方图:阈值应落在两峰之间。"""
        gray = np.array([10] * 50 + [200] * 50, dtype=np.uint8)
        t = _otsu_threshold(gray)
        assert 10 <= t <= 200

    def test_preprocess_returns_pil(self):
        engine = TesseractOcrEngine(OcrSection(engine="tesseract"))
        pil = engine._preprocess(solid_image(40, 20, (30, 30, 30)))
        assert pil.mode == "L"

    @pytest.mark.skipif(not TESSERACT_AVAILABLE, reason="本机未安装 tesseract")
    def test_recognize_digits_real_engine(self):
        """真实引擎识别数字文本(坐标条场景)。"""
        engine = TesseractOcrEngine(OcrSection(engine="tesseract", lang="eng"))
        result = engine.recognize(text_image("123,456"))
        assert result.success is True
        digits = "".join(ch for ch in result.value if ch.isdigit())
        assert "123" in digits
        assert 0.0 < result.confidence <= 1.0
        assert result.timestamp is not None

    def test_missing_binary_returns_failure(self, monkeypatch, tmp_path):
        """tesseract 路径指向不存在文件 → 失败结果而非异常。"""
        config = OcrSection(
            engine="tesseract", tesseract_cmd=str(tmp_path / "no_such_tesseract")
        )
        engine = TesseractOcrEngine(config)
        result = engine.recognize(text_image("abc"))
        assert result.success is False
        assert result.detail is not None


# ----------------------------------------------------------------------
# RuntimeRunner
# ----------------------------------------------------------------------


class TestRunnerBuild:
    def _runner(self, **kwargs) -> RuntimeRunner:
        return RuntimeRunner(
            settings=AppSettings(),
            profile=kwargs.pop("profile", _default_profile()),
            mock=True,
            sleep=lambda _s: None,
            **kwargs,
        )

    def test_build_mock_chain(self):
        runner = self._runner()
        machine = runner.build()
        assert isinstance(runner.adapter, MockGameAdapter)
        assert machine.adapter is runner.adapter

    def test_hotkeys_registered(self):
        runner = self._runner()
        runner.build()
        # W8 起注册 F10 紧急停止 + F8 暂停 + F9 恢复
        assert runner.hotkeys.registered_keys == ["F10", "F8", "F9"]

    def test_build_real_on_macos_raises(self):
        """real 模式在非 Windows 上组装失败并给出中文提示。"""
        runner = RuntimeRunner(
            settings=AppSettings(),
            profile=_default_profile(),
            mock=False,
            hotkeys=MockHotkeyManager(),
        )
        with pytest.raises(RunnerError, match="Windows"):
            runner.build()

    def test_ocr_engine_mock_by_default(self):
        runner = self._runner()
        machine = runner.build()
        # mock 模式下 adapter 是 MockGameAdapter,OCR 未被使用;
        # 直接验证 _build_ocr 路由
        assert isinstance(runner._build_ocr(), MockOcrEngine)

    def test_ocr_engine_tesseract_route(self):
        settings = AppSettings.from_dict(
            {"game": {"ocr": {"engine": "tesseract"}}}
        )
        runner = RuntimeRunner(
            settings=settings, profile=_default_profile(), mock=False,
            hotkeys=MockHotkeyManager(),
        )
        # real+tesseract → TesseractOcrEngine(不触发 Windows 绑定)
        assert isinstance(runner._build_ocr(), TesseractOcrEngine)


# ----------------------------------------------------------------------
# 闭环:W6 验收剧本
# ----------------------------------------------------------------------


class TestFullLoop:
    def _staged_runner(self, max_local_revive: int = 5) -> RuntimeRunner:
        runner = RuntimeRunner(
            settings=AppSettings(),
            profile=_default_profile(max_local_revive=max_local_revive),
            mock=True,
            sleep=lambda _s: None,
        )
        adapter = runner.build().adapter
        assert isinstance(adapter, MockGameAdapter)
        adapter.planned_deaths = max_local_revive + 1
        # 前 N 次原地复活成功;第 N+1 次死亡走 SAFE_REVIVE
        # (脚本耗尽后 revive 默认成功,回城并重新挂机)
        adapter.revive_script = [True] * max_local_revive
        return runner

    def test_full_loop_with_deaths(self):
        """挂机 → 死亡×6 → 5 原地复活 → 安全复活 → 回城 → 再挂机。"""
        runner = self._staged_runner()
        adapter = runner.adapter
        assert adapter is not None
        end_state = runner.run(max_ticks=200)
        # 闭环后回到 COMBAT(再挂机)
        assert end_state == "COMBAT"
        # 复活计数:5 次原地 + 安全复活后清零 + return_count=1
        assert adapter.calls.count(("local_revive", ())) == 5
        assert adapter.calls.count(("safe_revive", ())) == 1
        assert adapter.calls.count(("return_home", ())) == 1
        machine = runner.machine
        assert machine is not None
        assert machine.context.local_revive_count == 0
        assert machine.context.return_count == 1

    def test_hotkey_emergency_stop_mid_loop(self):
        """闭环中途按 F10 → 安全停止 → STOP。"""
        runner = self._staged_runner()
        machine = runner.machine
        assert machine is not None
        # 预埋:第 3 个 tick 按下 F10
        original_step = machine.step
        presses = {"n": 0}

        def fake_step() -> None:
            original_step()
            presses["n"] += 1
            if presses["n"] == 3:
                runner.hotkeys.press("F10")

        machine.step = fake_step  # type: ignore[method-assign]
        end_state = runner.run(max_ticks=100)
        assert end_state == "STOP"
        # 热键已注销(安全停止链路)
        assert runner.hotkeys.registered_keys == []

    def test_run_twice_reuses_machine(self):
        runner = self._staged_runner()
        runner.run(max_ticks=1)
        first_machine = runner.machine
        runner.run(max_ticks=1)
        assert runner.machine is first_machine


# ----------------------------------------------------------------------
# 辅助
# ----------------------------------------------------------------------


def _default_profile(max_local_revive: int = 5):
    from app.bootstrap import load_profile

    return load_profile()

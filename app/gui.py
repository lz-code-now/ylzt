"""tkinter 主窗口(W7)。

对应 DESIGN.md 第 18 节:主窗口含方案选择、地图/坐标、状态、
复活次数、运行时间、开始/暂停/停止按钮、运行日志。

线程模型(DESIGN 18,GUI 不阻塞状态机):

    tkinter mainloop(本类)
        ↓ root.after 每 200ms 轮询
    GuiBridge 快照 + GuiLogHandler 日志行 → 刷新控件
        ↓ start 时创建
    Worker 线程:RuntimeRunner.run() → 结束写 mark_finished

按钮语义:
- 开始:组装 RuntimeRunner 并启动 worker 线程(运行中禁用)
- 停止:.machine.request_stop()(安全停止链路,DESIGN 17 UI 停止层)
- 暂停/恢复:DESIGN 中 PAUSED 状态属 W8,本阶段禁用置灰
"""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

from app.gui_state import AppState, format_duration, GuiBridge, GuiLogHandler
from app.runner import RuntimeRunner
from models.profile import Profile
from models.settings import AppSettings
from utils.logger import get_logger, setup_logging

logger = get_logger("gui")

POLL_MS = 200  # 界面刷新周期


class GuiWindow:
    """主窗口:组装 UI 控件并驱动轮询刷新。"""

    def __init__(
        self,
        settings: AppSettings,
        profiles: dict[str, Profile],
        initial_profile: str = "default",
    ) -> None:
        self.settings = settings
        self.profiles = profiles
        self.bridge: GuiBridge | None = None
        self.log_handler: GuiLogHandler | None = None
        self.worker: threading.Thread | None = None
        self.runner: RuntimeRunner | None = None
        self._paused = False

        self.root = tk.Tk()
        self.root.title("御龙挂机助手")
        self.root.resizable(False, False)
        self._build_widgets(initial_profile)
        self.root.after(POLL_MS, self._poll)

    # ------------------------------------------------------------------
    # UI 构建
    # ------------------------------------------------------------------

    def _build_widgets(self, initial_profile: str) -> None:
        root = self.root
        # -- 方案选择 --
        top = ttk.LabelFrame(root, text="挂机方案", padding=8)
        top.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 4))
        self.profile_var = tk.StringVar(value=initial_profile)
        self.profile_box = ttk.Combobox(
            top,
            textvariable=self.profile_var,
            values=sorted(self.profiles),
            state="readonly",
            width=24,
        )
        self.profile_box.grid(row=0, column=0, padx=2)
        self.demo_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            top, text="演示模式(无需游戏)", variable=self.demo_var
        ).grid(row=0, column=1, padx=(8, 2))

        # -- 状态面板 --
        info = ttk.LabelFrame(root, text="运行状态", padding=8)
        info.grid(row=1, column=0, sticky="ew", padx=10, pady=4)
        self.labels: dict[str, tk.Label] = {}
        rows = [
            ("state", "状态"),
            ("map", "地图"),
            ("position", "当前坐标"),
            ("revive", "复活次数"),
            ("return", "回城次数"),
            ("errors", "异常次数"),
            ("elapsed", "运行时间"),
        ]
        for i, (key, title) in enumerate(rows):
            ttk.Label(info, text=f"{title}:").grid(row=i, column=0, sticky="w", pady=1)
            value = ttk.Label(info, text="-", width=32)
            value.grid(row=i, column=1, sticky="w", pady=1)
            self.labels[key] = value

        # -- 控制按钮 --
        buttons = ttk.Frame(root, padding=(10, 4))
        buttons.grid(row=2, column=0, sticky="ew")
        self.start_btn = ttk.Button(buttons, text="▶ 开始", command=self.on_start)
        self.start_btn.pack(side="left", padx=4)
        self.pause_btn = ttk.Button(buttons, text="⏸ 暂停", command=self.on_pause_toggle, state="disabled")
        self.pause_btn.pack(side="left", padx=4)
        self.stop_btn = ttk.Button(buttons, text="■ 停止", command=self.on_stop, state="disabled")
        self.stop_btn.pack(side="left", padx=4)

        # -- 日志区 --
        log_frame = ttk.LabelFrame(root, text="运行日志", padding=8)
        log_frame.grid(row=3, column=0, sticky="ew", padx=10, pady=(4, 10))
        self.log_text = ScrolledText(log_frame, height=12, width=56, state="disabled", font=("Menlo", 11))
        self.log_text.pack(fill="both", expand=True)

    # ------------------------------------------------------------------
    # 按钮动作
    # ------------------------------------------------------------------

    def on_start(self) -> None:
        """开始挂机:组装 runner 并启动 worker 线程。"""
        if self.worker is not None and self.worker.is_alive():
            return
        name = self.profile_var.get()
        profile = self.profiles[name]
        setup_logging(
            level=self.settings.logging.level,
            file_enabled=self.settings.logging.file_enabled,
        )
        self.bridge = GuiBridge(profile.name, profile.max_local_revive)
        self.log_handler = GuiLogHandler()
        logging.getLogger("ylzt").addHandler(self.log_handler)
        self.runner = RuntimeRunner(
            settings=self.settings,
            profile=profile,
            mock=self.demo_var.get(),  # 演示模式=mock;取消勾选则走真实适配器
        )
        self.worker = threading.Thread(target=self._run_worker, name="script-worker", daemon=True)
        self.start_btn.config(state="disabled")
        self.profile_box.config(state="disabled")
        self.pause_btn.config(state="normal")
        self.stop_btn.config(state="normal")
        logger.info("GUI 启动挂机: %s", profile.name)
        self.worker.start()

    def _run_worker(self) -> None:
        """worker 线程体:运行闭环,持续向桥写快照,结束写终态。"""
        assert self.runner is not None and self.bridge is not None
        machine = self.runner.build()

        original_step = machine.step

        def step_with_snapshot() -> None:
            original_step()
            self.bridge.update_context(machine.context)

        machine.step = step_with_snapshot  # type: ignore[method-assign]
        end_state = self.runner.run(max_ticks=400)
        self.bridge.mark_finished(end_state.name)

    def on_stop(self) -> None:
        """停止:走状态机安全停止链路(DESIGN 17 UI 停止层)。"""
        if self.runner is None or self.runner.machine is None:
            return
        logger.info("GUI 请求停止")
        self.runner.machine.request_stop()
        self.stop_btn.config(state="disabled")

    def on_pause_toggle(self) -> None:
        """暂停/恢复切换(W8):调用状态机 pause/resume。"""
        machine = self.runner.machine if self.runner else None
        if machine is None:
            return
        if self._paused:
            machine.resume()
            self._paused = False
            self.pause_btn.config(text="⏸ 暂停")
            logger.info("GUI 请求恢复")
        else:
            machine.pause()
            self._paused = True
            self.pause_btn.config(text="▶ 恢复")
            logger.info("GUI 请求暂停")

    def _not_ready(self) -> None:
        """暂未实现的功能提示。"""
        logger.info("该功能暂未实现")

    # ------------------------------------------------------------------
    # 轮询刷新
    # ------------------------------------------------------------------

    def _poll(self) -> None:
        """每 POLL_MS 刷新状态与日志(唯一触碰 UI 的路径)。"""
        if self.bridge is not None:
            self._refresh(self.bridge.snapshot())
        if self.log_handler is not None:
            self._append_logs(self.log_handler.poll())
        self.root.after(POLL_MS, self._poll)

    def _refresh(self, snap: AppState) -> None:
        def set_label(key: str, text: str) -> None:
            self.labels[key].config(text=text)

        set_label("state", snap.state_label)
        set_label("map", snap.map_name or "-")
        set_label(
            "position",
            f"{snap.current_x if snap.current_x is not None else '-'}, "
            f"{snap.current_y if snap.current_y is not None else '-'}"
            f"  (目标 {snap.target_x}, {snap.target_y})",
        )
        set_label("revive", f"{snap.local_revive_count} / {snap.max_local_revive}")
        set_label("return", str(snap.return_count))
        set_label("errors", str(snap.error_count))
        set_label("elapsed", format_duration(snap.running_seconds))
        if snap.finished:
            self.start_btn.config(state="normal")
            self.profile_box.config(state="readonly")
            self.pause_btn.config(state="disabled", text="⏸ 暂停")
            self._paused = False
            self.stop_btn.config(state="disabled")

    def _append_logs(self, lines: list[str]) -> None:
        if not lines:
            return
        self.log_text.config(state="normal")
        for line in lines:
            self.log_text.insert("end", line + "\n")
        # 只保留最近 400 行
        if int(self.log_text.index("end-1c").split(".")[0]) > 400:
            self.log_text.delete("1.0", f"{int(self.log_text.index('end-1c').split('.')[0]) - 400}.0")
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    # ------------------------------------------------------------------

    def run(self) -> None:
        """进入 tkinter 主循环;关闭窗口即退出。"""
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.mainloop()

    def _on_close(self) -> None:
        """关窗时请求安全停止并退出。"""
        if self.runner is not None and self.runner.machine is not None:
            self.runner.machine.request_stop()
        self.root.destroy()


def run_gui(settings: AppSettings, profiles: dict[str, Profile], initial_profile: str = "default") -> None:
    """GUI 入口:创建窗口并进入主循环。"""
    GuiWindow(settings, profiles, initial_profile).run()

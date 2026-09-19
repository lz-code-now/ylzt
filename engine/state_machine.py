"""状态机核心。

对应 DESIGN.md:

- 第 5 节:状态定义与转换表(13 个状态,STOP/ERROR 为终态)
- 第 10 节:坐标容差判断
- 第 13 节:死亡处理与复活逻辑(计数只在确认复活成功后才增加)
- 第 15 节:Watchdog 超时 → RECOVER
- 第 16 节:恢复重试有限,耗尽 → ERROR
- 第 17 节:安全停止(request_stop → 停止动作 → STOP)

业务逻辑只依赖 GameAdapter 接口(第 8 节),不接触真实游戏。
"""

from __future__ import annotations

import math
import time
from collections.abc import Callable
from datetime import datetime

from engine.exceptions import StateTransitionError
from engine.resilience import FailureTracker, RecoveryJournal, StuckDetector
from engine.watchdog import Watchdog
from game.adapter import GameAdapter
from models.profile import Profile
from models.runtime import RuntimeContext
from models.settings import AppSettings
from models.state import State, TERMINAL_STATES
from utils.logger import get_logger

logger = get_logger("engine")


class StateMachine:
    """规则驱动的脚本状态机。

    通过 ``step()`` 单步驱动,或 ``run()`` 循环运行至终态(STOP/ERROR)。
    ``state_history`` 记录全部状态转移(含初始状态),供测试与调试。
    """

    def __init__(
        self,
        adapter: GameAdapter,
        profile: Profile,
        settings: AppSettings | None = None,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """
        Args:
            adapter: 游戏适配器(W2 使用 MockGameAdapter)。
            profile: 挂机方案(目标坐标、复活上限、重试次数等)。
            settings: 应用设置;缺省时使用默认值。
            clock: 单调时钟函数,默认 time.monotonic;测试可注入假时钟。
        """
        self.adapter = adapter
        self.profile = profile
        self.settings = settings or AppSettings()
        self.context = RuntimeContext(
            target_x=profile.location.x,
            target_y=profile.location.y,
        )
        # NAVIGATE 超时使用挂机方案的寻路超时,其余状态用默认超时表
        self.watchdog = Watchdog(
            {State.NAVIGATE: profile.navigation.timeout_seconds},
            clock=clock,
        )
        self.watchdog.on_state_entered(State.INIT)
        self.state_history: list[State] = [State.INIT]
        self._stop_requested = False
        self._pause_requested = False
        self._combat_start_attempts = 0
        self._recover_reason = "未指定原因"
        # W8 异常恢复组件(DESIGN 15/16/17)
        runtime = self.settings.runtime
        self.stuck_detector = StuckDetector(
            runtime.stuck_check_interval_seconds,
            runtime.stuck_min_distance,
            clock=clock,
        )
        self.failure_tracker = FailureTracker(runtime.max_consecutive_failures)
        self.recovery_journal = RecoveryJournal(
            runtime.debug_dir, runtime.max_recovery_screenshot
        )
        self._handlers: dict[State, Callable[[RuntimeContext], State]] = {
            State.INIT: self._handle_init,
            State.CHECK_GAME: self._handle_check_game,
            State.CHECK_MAP: self._handle_check_map,
            State.NAVIGATE: self._handle_navigate,
            State.START_COMBAT: self._handle_start_combat,
            State.COMBAT: self._handle_combat,
            State.DEAD: self._handle_dead,
            State.LOCAL_REVIVE: self._handle_local_revive,
            State.SAFE_REVIVE: self._handle_safe_revive,
            State.RETURN_HOME: self._handle_return_home,
            State.RECOVER: self._handle_recover,
        }

    # ------------------------------------------------------------------
    # 公开 API
    # ------------------------------------------------------------------

    def request_stop(self) -> None:
        """请求安全停止:下一个 step 先停止游戏内动作,再进入 STOP。"""
        self._stop_requested = True

    def pause(self) -> None:
        """请求暂停(DESIGN 17 UI 层):下一个 step 进入 PAUSED。"""
        self._pause_requested = True

    def resume(self) -> None:
        """请求恢复:从 PAUSED 回到 CHECK_GAME 重新确认游戏状态。"""
        self._pause_requested = False

    def run(self, max_ticks: int | None = None) -> State:
        """循环执行直到进入终态或达到 max_ticks。

        Args:
            max_ticks: 最大执行步数(防死循环保护);None 表示不限制。

        Returns:
            结束时的状态(终态,或 max_ticks 用尽时的当前状态)。
        """
        ticks = 0
        while self.context.state not in TERMINAL_STATES:
            if max_ticks is not None and ticks >= max_ticks:
                break
            self.step()
            ticks += 1
        return self.context.state

    def step(self) -> State:
        """执行一个状态处理步骤,返回执行后的当前状态。

        顺序:停止请求 → Watchdog 超时 → 当前状态的处理逻辑。
        """
        state = self.context.state
        if state in TERMINAL_STATES:
            raise StateTransitionError(
                f"状态机已处于终态 {state.value},不能再执行 step"
            )
        if self._stop_requested:
            self._safe_stop()
            return self.context.state
        if self._pause_requested and state is not State.PAUSED:
            self._transit_to(State.PAUSED)
            return self.context.state
        if state is State.PAUSED:
            # 暂停中:停留,等待 resume 或 stop;恢复由 resume() 触发转移
            if self._pause_requested:
                return self.context.state
            logger.info("Resuming from pause -> CHECK_GAME")
            self._transit_to(State.CHECK_GAME)
            return self.context.state
        if self.watchdog.check(state):
            logger.warning("State %s timed out -> RECOVER", state.value)
            self._recover_reason = f"状态超时: {state.value}"
            self._transit_to(State.RECOVER)
            return self.context.state
        next_state = self._handlers[state](self.context)
        if next_state is not state:
            self._transit_to(next_state)
        return self.context.state

    # ------------------------------------------------------------------
    # 内部:状态转移与安全停止
    # ------------------------------------------------------------------

    def _transit_to(self, state: State) -> None:
        logger.info("State %s -> %s", self.context.state.value, state.value)
        if state is State.START_COMBAT:
            # 重新进入开启战斗时,重置开启尝试计数
            self._combat_start_attempts = 0
        if state is not State.NAVIGATE:
            # 离开导航场景时清空卡住检测采样
            self.stuck_detector.reset()
        self.context.transit_to(state)
        self.watchdog.on_state_entered(state)
        self.state_history.append(state)

    def _safe_stop(self) -> None:
        """安全停止(DESIGN 17):先停止游戏内战斗动作,再进入 STOP。"""
        logger.info("Safe stop requested")
        try:
            self.adapter.stop_combat()
        finally:
            self._transit_to(State.STOP)

    # ------------------------------------------------------------------
    # 各状态处理(DESIGN 5.2 转换表)
    # ------------------------------------------------------------------

    def _handle_init(self, ctx: RuntimeContext) -> State:
        logger.info(
            "Engine init, target=(%s, %s), max_local_revive=%d",
            ctx.target_x,
            ctx.target_y,
            self.profile.max_local_revive,
        )
        return State.CHECK_GAME

    def _handle_check_game(self, ctx: RuntimeContext) -> State:
        if not self.adapter.is_game_running():
            ctx.error_count += 1
            logger.error("Game is not running -> ERROR")
            return State.ERROR
        self.adapter.activate_game()
        return State.CHECK_MAP

    def _handle_check_map(self, ctx: RuntimeContext) -> State:
        map_name = self.adapter.get_current_map()
        if map_name is None:
            self._record_identify_failure(ctx, "CHECK_MAP", "无法读取地图名")
            return State.RECOVER
        self.failure_tracker.record_success()
        ctx.map_name = map_name
        logger.info("Current map: %s", map_name)
        # 地图正确与否都进入寻路(DESIGN 5.2)
        return State.NAVIGATE

    def _handle_navigate(self, ctx: RuntimeContext) -> State:
        self.adapter.navigate_to(ctx.target_x, ctx.target_y)
        position = self.adapter.get_position()
        if position is None:
            self._record_identify_failure(ctx, "NAVIGATE", "无法读取坐标")
            return State.RECOVER
        ctx.current_x, ctx.current_y = position
        if self._arrived(position):
            logger.info("Target reached")
            ctx.last_successful_action = "navigate"
            self.failure_tracker.record_success()
            return State.START_COMBAT
        # 未到达:先查卡住(DESIGN 15),再交给 Watchdog 超时(DESIGN 11)
        if self.stuck_detector.check(position):
            return self._enter_recover(ctx, "NAVIGATE", "导航卡住")
        return State.NAVIGATE

    def _arrived(self, position: tuple[int, int]) -> bool:
        """DESIGN 第 10 节:欧氏距离 <= 容差即视为到达。"""
        location = self.profile.location
        distance = math.hypot(position[0] - location.x, position[1] - location.y)
        return distance <= location.tolerance

    def _handle_start_combat(self, ctx: RuntimeContext) -> State:
        if self.adapter.is_auto_combat_enabled():
            return State.COMBAT
        retry_limit = self.profile.combat.start_retry_count
        if self._combat_start_attempts >= retry_limit:
            self._combat_start_attempts = 0
            ctx.error_count += 1
            logger.warning(
                "Auto combat start failed after %d retries -> RECOVER", retry_limit
            )
            self._recover_reason = "自动战斗启动失败"
            return State.RECOVER
        self._combat_start_attempts += 1
        self.adapter.start_auto_combat()
        if self.adapter.is_auto_combat_enabled():
            ctx.last_successful_action = "start_auto_combat"
            logger.info("Auto combat enabled")
            return State.COMBAT
        logger.warning(
            "Auto combat start attempt %d/%d failed",
            self._combat_start_attempts,
            retry_limit,
        )
        return State.START_COMBAT

    def _handle_combat(self, ctx: RuntimeContext) -> State:
        # COMBAT 无固定超时,但每步做健康检查(DESIGN 15)
        if not self.adapter.is_game_running():
            logger.warning("Game lost during combat -> RECOVER")
            self._recover_reason = "COMBAT: 游戏窗口丢失"
            return State.RECOVER
        if self.adapter.is_dead():
            ctx.last_death_at = datetime.now()
            logger.warning("Player dead")
            return State.DEAD
        return State.COMBAT

    def _handle_dead(self, ctx: RuntimeContext) -> State:
        self.adapter.stop_combat()
        max_local = self.profile.max_local_revive
        if ctx.local_revive_count < max_local:
            logger.info(
                "Plan local revive (%d/%d used)", ctx.local_revive_count, max_local
            )
            return State.LOCAL_REVIVE
        logger.info("Local revive limit reached, use safe revive")
        return State.SAFE_REVIVE

    def _handle_local_revive(self, ctx: RuntimeContext) -> State:
        self.adapter.local_revive()
        if self.adapter.is_dead():
            logger.warning("Local revive failed -> RECOVER")
            self._recover_reason = "LOCAL_REVIVE: 原地复活失败"
            return State.RECOVER
        # DESIGN 13.2:计数器只在确认复活成功后才增加
        ctx.local_revive_count += 1
        ctx.last_successful_action = "local_revive"
        logger.info(
            "Local revive %d/%d",
            ctx.local_revive_count,
            self.profile.max_local_revive,
        )
        return State.NAVIGATE

    def _handle_safe_revive(self, ctx: RuntimeContext) -> State:
        self.adapter.safe_revive()
        if self.adapter.is_dead():
            logger.warning("Safe revive failed -> RECOVER")
            self._recover_reason = "SAFE_REVIVE: 安全复活失败"
            return State.RECOVER
        # DESIGN 13.2:安全复活成功后,原地复活计数清零,回城计数 +1
        ctx.local_revive_count = 0
        ctx.return_count += 1
        ctx.last_successful_action = "safe_revive"
        logger.info("Safe revive done, return count %d", ctx.return_count)
        return State.RETURN_HOME

    def _handle_return_home(self, ctx: RuntimeContext) -> State:
        self.adapter.return_home()
        if not self.adapter.is_game_running() or self.adapter.get_current_map() is None:
            logger.warning("Return home failed -> RECOVER")
            self._recover_reason = "RETURN_HOME: 回城后状态确认失败"
            return State.RECOVER
        ctx.last_successful_action = "return_home"
        logger.info("Returned home")
        return State.NAVIGATE

    def _handle_recover(self, ctx: RuntimeContext) -> State:
        max_recovery = self.profile.recovery.max_recovery_count
        if ctx.recovery_count >= max_recovery:
            ctx.error_count += 1
            logger.error("Recovery retries exhausted -> ERROR")
            return State.ERROR
        ctx.recovery_count += 1
        # DESIGN 16 五要素:时间/状态/原因/截图/重试次数
        self.recovery_journal.record(
            state=State.RECOVER,
            reason=self._recover_reason,
            retry_index=ctx.recovery_count,
            screenshot=self.adapter.capture_screenshot(),
        )
        logger.warning(
            "Recovering, attempt %d/%d", ctx.recovery_count, max_recovery
        )
        if self.adapter.is_game_running():
            # 恢复成功:重置连续恢复计数,回到 CHECK_GAME(DESIGN 16)
            ctx.recovery_count = 0
            ctx.last_successful_action = "recover"
            return State.CHECK_GAME
        # 恢复失败:留在 RECOVER,下一轮继续重试
        return State.RECOVER

    # ------------------------------------------------------------------
    # 内部:异常恢复辅助(W8)
    # ------------------------------------------------------------------

    def _record_identify_failure(
        self, ctx: RuntimeContext, where: str, reason: str
    ) -> None:
        """识别失败:累计连续失败并按阈值决定 RECOVER 或自动安全停止。"""
        ctx.error_count += 1
        count = self.failure_tracker.record_failure()
        logger.warning("%s 识别失败(连续 %d/%d)", where, count, self.failure_tracker.threshold)
        if self.failure_tracker.exceeded:
            # DESIGN 17 自动安全停止:连续异常达到阈值
            self._stop_requested = True

    def _enter_recover(
        self, ctx: RuntimeContext, where: str, reason: str
    ) -> State:
        """带原因进入 RECOVER(供事件记录)。"""
        self._recover_reason = f"{where}: {reason}"
        return State.RECOVER

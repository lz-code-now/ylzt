"""状态机 + MockGameAdapter 测试。

覆盖 DESIGN.md 20.1 节要求:状态转换、复活计数(0/4/5/>5)、
达到复活上限后的行为、超时、重试、STOP、ERROR;
以及 21 节 W2 验收:完整模拟挂机循环。

说明:DESIGN 13.2 伪代码为 ``local_revive_count < max_local_revive`` 时原地复活,
因此 max_local_revive=5 时,第 1~5 次死亡均原地复活,第 6 次死亡触发安全复活。
"""

from __future__ import annotations

import pytest

from engine.exceptions import StateTransitionError
from engine.state_machine import StateMachine
from game.mock_adapter import MockGameAdapter
from models.profile import Location, Profile
from models.state import State


def run_until(sm: StateMachine, target: State, max_steps: int = 100) -> bool:
    """单步执行直到进入目标状态;返回是否到达。"""
    for _ in range(max_steps):
        if sm.context.state is target:
            return True
        if sm.context.state in (State.STOP, State.ERROR):
            return False
        sm.step()
    return sm.context.state is target


# ----------------------------------------------------------------------
# MockGameAdapter 自身行为(DESIGN 20.2 场景)
# ----------------------------------------------------------------------


class TestMockGameAdapter:
    def test_default_navigate_arrives_immediately(self):
        adapter = MockGameAdapter(position=(0, 0))
        adapter.navigate_to(100, 200)
        assert adapter.get_position() == (100, 200)

    def test_planned_death_only_triggers_in_combat(self):
        adapter = MockGameAdapter()
        adapter.planned_deaths = 1
        # 未在战斗中:不会死亡
        assert adapter.is_dead() is False
        # 进入战斗后死亡
        adapter.auto_combat_enabled = True
        assert adapter.is_dead() is True
        # 死亡状态持续,直到复活
        assert adapter.is_dead() is True
        adapter.local_revive()
        assert adapter.is_dead() is False

    def test_revive_failure_keeps_dead(self):
        adapter = MockGameAdapter()
        adapter.planned_deaths = 1
        adapter.auto_combat_enabled = True
        assert adapter.is_dead() is True
        adapter.revive_script = [False]
        adapter.local_revive()
        assert adapter.is_dead() is True

    def test_game_closed(self):
        adapter = MockGameAdapter()
        adapter.game_running = False
        assert adapter.is_game_running() is False
        assert adapter.get_current_map() is None
        assert adapter.get_position() is None

    def test_calls_are_recorded(self):
        adapter = MockGameAdapter()
        adapter.navigate_to(1, 2)
        assert adapter.called("navigate_to") == 1
        assert adapter.was_called_with("navigate_to", (1, 2))


# ----------------------------------------------------------------------
# W2 验收:完整模拟循环
# ----------------------------------------------------------------------


class TestFullLoop:
    def test_full_loop_local_revives_then_safe_revive(self, profile):
        """完整闭环:战斗 → 死亡×5(原地复活)→ 第 6 次死亡 → 安全复活 → 回城 → 重新挂机。"""
        adapter = MockGameAdapter(map_name="目标地图", position=(0, 0))
        adapter.planned_deaths = 6
        sm = StateMachine(adapter, profile)

        final = sm.run(max_ticks=200)
        assert final is State.COMBAT

        history = sm.state_history
        # 启动主链路
        assert history[:6] == [
            State.INIT,
            State.CHECK_GAME,
            State.CHECK_MAP,
            State.NAVIGATE,
            State.START_COMBAT,
            State.COMBAT,
        ]
        # 死亡与复活
        assert history.count(State.DEAD) == 6
        assert history.count(State.LOCAL_REVIVE) == 5
        assert history.count(State.SAFE_REVIVE) == 1
        assert history.count(State.RETURN_HOME) == 1
        # 全程无异常
        assert history.count(State.RECOVER) == 0
        assert history.count(State.ERROR) == 0
        assert history.count(State.STOP) == 0
        # 安全复活后:原地复活计数清零,回城计数 +1(DESIGN 13.2)
        assert sm.context.local_revive_count == 0
        assert sm.context.return_count == 1
        assert sm.context.error_count == 0
        # 适配器调用
        assert adapter.called("local_revive") == 5
        assert adapter.called("safe_revive") == 1
        assert adapter.called("return_home") == 1
        # 回城后重新寻路并回到战斗(DESIGN 14)
        return_home_index = history.index(State.RETURN_HOME)
        assert history[return_home_index + 1] is State.NAVIGATE
        # 运行时上下文记录
        assert sm.context.last_death_at is not None
        assert sm.context.last_successful_action == "start_auto_combat"
        assert sm.context.map_name == "目标地图"
        assert (sm.context.current_x, sm.context.current_y) == (100, 200)


# ----------------------------------------------------------------------
# 导航与到达判断(DESIGN 10)
# ----------------------------------------------------------------------


class TestNavigation:
    def test_arrive_within_tolerance(self, profile):
        adapter = MockGameAdapter()
        # 距目标 (100,200) 约 8 <= 容差 10:视为到达
        adapter.navigate_script = [(108, 200)]
        sm = StateMachine(adapter, profile)
        assert run_until(sm, State.START_COMBAT)
        assert sm.state_history[-1] is State.START_COMBAT

    def test_not_arrived_stays_in_navigate(self, profile):
        adapter = MockGameAdapter()
        # 距目标 (100,200) 15 > 容差 10:未到达
        adapter.navigate_script = [(115, 200)] * 20
        sm = StateMachine(adapter, profile)
        assert run_until(sm, State.NAVIGATE)
        sm.step()
        sm.step()
        assert sm.context.state is State.NAVIGATE
        assert (sm.context.current_x, sm.context.current_y) == (115, 200)

    def test_navigate_timeout_goes_recover_then_check_game(self, profile, fake_clock):
        adapter = MockGameAdapter()
        adapter.navigate_script = [(9999, 9999)] * 50  # 永远到不了
        sm = StateMachine(adapter, profile, clock=fake_clock)
        assert run_until(sm, State.NAVIGATE)

        fake_clock.advance(profile.navigation.timeout_seconds)
        sm.step()
        assert sm.context.state is State.RECOVER

        # 游戏仍在运行:恢复成功 → CHECK_GAME,并重置连续恢复计数
        sm.step()
        assert sm.context.state is State.CHECK_GAME
        assert sm.context.recovery_count == 0


# ----------------------------------------------------------------------
# 复活决策与计数(DESIGN 13.2 / 20.1 重点)
# ----------------------------------------------------------------------


class TestReviveDecisions:
    @pytest.mark.parametrize(
        ("count", "expected"),
        [
            (0, State.LOCAL_REVIVE),
            (4, State.LOCAL_REVIVE),
            (5, State.SAFE_REVIVE),
            (6, State.SAFE_REVIVE),  # 超出上限的防御场景
        ],
    )
    def test_dead_branches_on_local_revive_count(
        self, profile, count, expected
    ):
        adapter = MockGameAdapter()
        sm = StateMachine(adapter, profile)
        sm.context.local_revive_count = count
        sm.context.transit_to(State.DEAD)
        sm.watchdog.on_state_entered(State.DEAD)
        sm.step()
        assert sm.context.state is expected

    def test_local_revive_failure_goes_recover_and_retries(self, profile):
        adapter = MockGameAdapter()
        adapter.planned_deaths = 1
        adapter.revive_script = [False]  # 第一次复活失败
        sm = StateMachine(adapter, profile)

        assert run_until(sm, State.RECOVER)
        # 复活失败:计数不增加(DESIGN 13.2)
        assert sm.context.local_revive_count == 0
        assert adapter.called("local_revive") == 1

        # 恢复后重新走流程:再次发现死亡 → 原地复活成功 → 回到战斗
        final = sm.run(max_ticks=100)
        assert final is State.COMBAT
        assert sm.context.local_revive_count == 1
        assert adapter.called("local_revive") == 2
        assert sm.state_history.count(State.RECOVER) == 1

    def test_safe_revive_resets_local_count(self, profile):
        adapter = MockGameAdapter()
        adapter.planned_deaths = 1
        sm = StateMachine(adapter, profile)
        run_until(sm, State.COMBAT)
        # 战斗中死亡,且原地复活次数已达上限
        sm.context.local_revive_count = profile.max_local_revive
        assert run_until(sm, State.SAFE_REVIVE)
        sm.step()
        assert sm.context.state is State.RETURN_HOME
        assert sm.context.local_revive_count == 0
        assert sm.context.return_count == 1


# ----------------------------------------------------------------------
# 重试、STOP、ERROR(DESIGN 16、17、20.1)
# ----------------------------------------------------------------------


class TestStopAndError:
    def test_request_stop_enters_stop_and_stops_combat(self, profile):
        adapter = MockGameAdapter()
        sm = StateMachine(adapter, profile)
        assert run_until(sm, State.COMBAT)

        sm.request_stop()
        final = sm.run(max_ticks=5)
        assert final is State.STOP
        assert sm.state_history[-1] is State.STOP
        # 安全停止会先停止游戏内战斗动作(DESIGN 17)
        assert adapter.called("stop_combat") >= 1
        assert adapter.auto_combat_enabled is False

    def test_step_after_terminal_raises(self, profile):
        adapter = MockGameAdapter()
        adapter.game_running_script = [False]
        sm = StateMachine(adapter, profile)
        assert sm.run(max_ticks=10) is State.ERROR
        with pytest.raises(StateTransitionError):
            sm.step()

    def test_game_not_running_goes_error(self, profile):
        adapter = MockGameAdapter()
        adapter.game_running_script = [False]
        sm = StateMachine(adapter, profile)
        final = sm.run(max_ticks=10)
        assert final is State.ERROR
        assert sm.state_history == [State.INIT, State.CHECK_GAME, State.ERROR]
        assert sm.context.error_count == 1

    def test_recovery_exhausted_goes_error(self, profile):
        adapter = MockGameAdapter()
        # 前两次检查游戏在运行(启动 + 首次战斗健康检查),之后一直关闭
        adapter.game_running_script = [True, True] + [False] * 20
        sm = StateMachine(adapter, profile)
        final = sm.run(max_ticks=100)
        assert final is State.ERROR
        assert sm.context.error_count == 1
        # 恢复尝试次数 = max_recovery_count(3),耗尽后进入 ERROR
        assert adapter.called("is_game_running") >= 3

    def test_start_combat_retry_exhausted_goes_recover(self, profile):
        adapter = MockGameAdapter()
        adapter.auto_combat_script = [False] * 10  # 开启始终失败
        sm = StateMachine(adapter, profile)
        assert run_until(sm, State.RECOVER)
        # 重试次数用尽才转入 RECOVER
        assert adapter.called("start_auto_combat") == profile.combat.start_retry_count
        assert sm.context.error_count == 1

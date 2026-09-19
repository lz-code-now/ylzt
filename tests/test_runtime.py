"""State / RuntimeContext / Watchdog 单元测试(DESIGN 5.1、6.1、15)。"""

from __future__ import annotations

from datetime import datetime

from engine.watchdog import Watchdog
from models.runtime import RuntimeContext
from models.state import TERMINAL_STATES, State

EXPECTED_STATES = [
    "INIT",
    "CHECK_GAME",
    "CHECK_MAP",
    "NAVIGATE",
    "START_COMBAT",
    "COMBAT",
    "DEAD",
    "LOCAL_REVIVE",
    "SAFE_REVIVE",
    "RETURN_HOME",
    "RECOVER",
    "PAUSED",
    "STOP",
    "ERROR",
]


class TestStateEnum:
    def test_has_14_members_in_design_order(self):
        """DESIGN 5.1 的 13 个业务状态 + W8 新增的 PAUSED 运行控制状态。"""
        assert [s.name for s in State] == EXPECTED_STATES
        assert len(State) == 14

    def test_terminal_states_are_stop_and_error(self):
        assert set(TERMINAL_STATES) == {State.STOP, State.ERROR}


class TestRuntimeContext:
    def test_defaults(self):
        ctx = RuntimeContext()
        assert ctx.state is State.INIT
        assert ctx.map_name is None
        assert ctx.current_x is None
        assert ctx.current_y is None
        assert ctx.target_x is None
        assert ctx.target_y is None
        assert ctx.local_revive_count == 0
        assert ctx.return_count == 0
        assert ctx.error_count == 0
        assert ctx.recovery_count == 0
        assert isinstance(ctx.started_at, datetime)
        assert isinstance(ctx.last_state_change_at, datetime)
        assert ctx.last_successful_action is None
        assert ctx.last_death_at is None

    def test_transit_to_updates_state_and_timestamp(self):
        ctx = RuntimeContext()
        before = ctx.last_state_change_at
        ctx.transit_to(State.COMBAT)
        assert ctx.state is State.COMBAT
        assert ctx.last_state_change_at >= before


class TestWatchdog:
    def test_timeout_triggers_after_configured_seconds(self, fake_clock):
        watchdog = Watchdog({State.NAVIGATE: 5}, clock=fake_clock)
        watchdog.on_state_entered(State.NAVIGATE)
        fake_clock.advance(4.9)
        assert watchdog.check(State.NAVIGATE) is False
        fake_clock.advance(0.1)
        assert watchdog.check(State.NAVIGATE) is True

    def test_zero_timeout_means_no_fixed_limit(self, fake_clock):
        # DESIGN 15:combat: 0 表示没有固定超时
        watchdog = Watchdog(clock=fake_clock)
        watchdog.on_state_entered(State.COMBAT)
        fake_clock.advance(100000)
        assert watchdog.check(State.COMBAT) is False

    def test_entering_state_restarts_timer(self, fake_clock):
        watchdog = Watchdog({State.NAVIGATE: 10}, clock=fake_clock)
        watchdog.on_state_entered(State.NAVIGATE)
        fake_clock.advance(9)
        watchdog.on_state_entered(State.NAVIGATE)
        fake_clock.advance(9)
        assert watchdog.check(State.NAVIGATE) is False
        fake_clock.advance(1)
        assert watchdog.check(State.NAVIGATE) is True

    def test_default_timeout_table_matches_design(self, fake_clock):
        watchdog = Watchdog(clock=fake_clock)
        assert dict(watchdog.DEFAULT_TIMEOUTS) == {
            State.CHECK_GAME: 10,
            State.CHECK_MAP: 10,
            State.NAVIGATE: 180,
            State.START_COMBAT: 10,
            State.COMBAT: 0,
            State.LOCAL_REVIVE: 20,
            State.SAFE_REVIVE: 20,
            State.RETURN_HOME: 60,
            State.RECOVER: 0,
        }

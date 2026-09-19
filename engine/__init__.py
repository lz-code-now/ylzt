"""Engine 层:状态机、超时、重试、停止机制。

- state_machine.py:StateMachine(W2;W8 接入 PAUSED/卡住/连续失败/恢复事件)
- watchdog.py:Watchdog 状态超时(W2)
- resilience.py:异常恢复辅助——卡住检测/连续失败/恢复事件与截图(W8)
- exceptions.py:EngineError/StateTransitionError(W2)
"""

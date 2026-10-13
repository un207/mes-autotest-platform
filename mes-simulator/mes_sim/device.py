"""设备行为模型 —— 让寄存器"动起来"。

真实设备的寄存器值由 PLC 程序按工艺逻辑更新。模拟器要像样，就得有这层逻辑：
产量按节拍递增、温度围绕基准随机游走、状态在停机/运行/故障之间迁移。

设计取舍：
  - 直接持有服务端的寄存器列表（同一对象引用），tick 时写入。
    好处是不需要额外的"业务状态 → 寄存器"同步步骤，也不存在两份数据不一致的可能。
  - 随机数用可注入的 Random 实例，便于测试时给定种子复现同一串数据。
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from . import registers as R


@dataclass
class DeviceProfile:
    """设备工况档案 —— 决定这台设备"怎么干活"。"""

    cycle_seconds: float = 6.0
    """生产节拍：每件耗时（秒）。"""

    base_temperature: float = 24.0
    """基准温度（℃）。"""

    temperature_drift: float = 0.6
    """每个 tick 的温度漂移幅度（℃），围绕基准做随机游走。"""

    temperature_limit: float = 78.0
    """温度上限：超过则转故障态（模拟过热停机）。"""

    defect_rate: float = 0.03
    """不良率，决定良品/不良的分配。"""

    startup_minutes: int = 0
    """启动时已运行时长，便于快速造出"已跑了一段时间"的数据。"""


@dataclass
class DeviceSimulator:
    """单台设备的运行逻辑。"""

    equipment_code: str
    line_code: str
    register_block: list[int]
    """与 Modbus 服务端共享的寄存器列表（同一引用，直接改写即生效）。"""

    profile: DeviceProfile = field(default_factory=DeviceProfile)
    rng: random.Random = field(default_factory=random.Random)

    # ---- 内部运行状态 ----
    _output: int = 0
    _qualified: int = 0
    _defective: int = 0
    _temperature: float = 0.0
    _cycle_progress: float = 0.0
    _run_seconds: float = 0.0
    _status: int = 1
    _fault_code: int = 0
    _started: bool = False

    # ------------------------------------------------------------------ 生命周期

    def start(self) -> None:
        """开机：置运行态、温度落到基准、写入初始寄存器。"""
        self._temperature = self.profile.base_temperature
        self._run_seconds = self.profile.startup_minutes * 60.0
        self._status = 1
        self._fault_code = 0
        self._started = True
        self._flush()

    def stop(self) -> None:
        """停机（模拟下班/换班）。"""
        self._status = 0
        self._flush()

    def resume(self) -> None:
        self._status = 1
        self._flush()

    def seed_counters(self, output: int) -> None:
        """用历史累计产量初始化计数器，模拟「设备未断电、计数延续」。

        模拟器每次启动都从 0 开始计数，而现场设备的产量计数器通常掉电保持。
        不延续的话，列表里会出现「上次累计到 3、这次从 0 开始」的回落，像是数据错误。

        良品与不良按设定不良率拆分：这两项在点表里不上报，仅用于设备内部状态展示，
        MES 侧没有可回查的历史，因此按比例还原一个合理的起始分布。
        """
        self._output = max(0, int(output))
        qualified = int(round(self._output * (1 - self.profile.defect_rate)))
        self._qualified = qualified
        self._defective = self._output - qualified

    # ------------------------------------------------------------------ 推进

    def tick(self, elapsed: float) -> None:
        """推进 elapsed 秒。这是模拟器的心跳，由控制循环周期调用。"""
        if not self._started or elapsed <= 0:
            return

        if self._status == 0:
            # 停机：温度缓慢回落到环境温度，其余不动
            self._temperature += (self.profile.base_temperature - self._temperature) * 0.05
            self._flush()
            return

        if self._status == 2:
            # 故障：温度回落（已停机散热），不产出
            self._temperature += (self.profile.base_temperature - self._temperature) * 0.08
            self._flush()
            return

        # ---- 运行态 ----
        self._run_seconds += elapsed

        # 温度：随机游走 + 向基准回归，避免无限漂移
        drift = self.rng.uniform(-self.profile.temperature_drift, self.profile.temperature_drift)
        pull = (self.profile.base_temperature - self._temperature) * 0.08
        self._temperature = round(self._temperature + drift + pull, 2)

        # 过热保护：超过上限转故障态
        if self._temperature >= self.profile.temperature_limit:
            self._status = 2
            self._fault_code = 1  # 1 = 过热
            self._flush()
            return

        # 产出：按节拍累积
        self._cycle_progress += elapsed
        while self._cycle_progress >= self.profile.cycle_seconds:
            self._cycle_progress -= self.profile.cycle_seconds
            self._output += 1
            if self.rng.random() < self.profile.defect_rate:
                self._defective += 1
            else:
                self._qualified += 1

        self._flush()

    # ------------------------------------------------------------------ 异常注入支撑

    def force_fault(self, code: int = 1) -> None:
        """强制进入故障态（供异常场景使用）。"""
        self._status = 2
        self._fault_code = code
        self._flush()

    def clear_fault(self) -> None:
        self._status = 1 if self._started else 0
        self._fault_code = 0
        self._flush()

    # ------------------------------------------------------------------ 寄存器读写

    def _write(self, name: str, raw: int) -> None:
        self.register_block[R.address_of(name)] = max(0, min(0xFFFF, int(raw)))

    def read_raw(self, name: str) -> int:
        return self.register_block[R.address_of(name)]

    def _flush(self) -> None:
        """把业务状态写进寄存器块。"""
        self._write("OUTPUT_COUNT", self._output)
        self._write("RUN_STATUS", self._status)
        self._write("TEMPERATURE", R.BY_NAME["TEMPERATURE"].to_raw(self._temperature))
        self._write("QUALIFIED_COUNT", self._qualified)
        self._write("DEFECTIVE_COUNT", self._defective)
        self._write("CYCLE_TIME", int(self.profile.cycle_seconds))
        self._write("RUN_MINUTES", int(self._run_seconds // 60))
        self._write("FAULT_CODE", self._fault_code)

    # ------------------------------------------------------------------ 只读快照

    def snapshot(self) -> dict[str, object]:
        """当前状态的只读快照，供日志与界面展示。"""
        return {
            "equipmentCode": self.equipment_code,
            "lineCode": self.line_code,
            "status": self._status,
            "statusLabel": {0: "停机", 1: "运行", 2: "故障"}.get(self._status, "未知"),
            "output": self._output,
            "qualified": self._qualified,
            "defective": self._defective,
            "temperature": round(self._temperature, 1),
            "runMinutes": int(self._run_seconds // 60),
            "faultCode": self._fault_code,
        }

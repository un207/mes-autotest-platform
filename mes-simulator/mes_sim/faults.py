"""异常数据注入 —— 故意制造坏数据，用来验证 MES 的数采质量把关。

为什么需要它：MES 的数采入口做了三层把关（可解析性 → 工况区间 → 时间合理性），
如果模拟器永远只发正常数据，这三层逻辑就从未被真正走通过。只有主动注入异常，
才能证明把关是有效的 —— 这也是「设备侧异常」在真实项目里必须被覆盖的原因。

注入分两层，这不是为了复杂而复杂，而是协议本身的限制决定的：

  ① 设备侧（改 Modbus 寄存器）
     Modbus 保持寄存器是 16 位无符号整数，**装不下负数和超过 65535 的值**。
     所以只有"在 0~65535 范围内的非法工况值"能从这里注入，例如状态码 99、温度 512℃。

  ② 采集侧（改上报的原始串）
     现场网关把寄存器值转成字符串上报。传感器故障、通信错误这类情况，
     设备根本没有有效值可给，网关上报的是错误标记串（"ERR"、"####"）。
     另外像"产量超过一百万"这种超出 16 位表示能力的场景，也只能在这一层构造。

两层注入都对应真实的故障形态，不是凭空造的测试数据。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from . import registers as R
from .device import DeviceSimulator

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class FaultScenario:
    """一个异常场景。"""

    key: str
    label: str
    desc: str
    metric: R.Metric
    expect_flag: str
    """预期 MES 判定的质量标记：BAD（不可解析）或 SUSPECT（可疑）。"""

    expect_reason_hint: str
    """预期判定原因的线索词，用于自检时校验 MES 给出的原因确实对得上。"""

    target: str
    """注入层：device（改寄存器）或 collector（改上报串）。"""

    register_name: str | None = None
    register_value: int | None = None
    raw_payload: str | None = None
    clock_offset_hours: float | None = None


SCENARIOS: dict[str, FaultScenario] = {
    s.key: s
    for s in (
        FaultScenario(
            key="temp_overheat",
            label="设备过热",
            desc="主轴温度冲到 512℃（寄存器存 5120），远超 MES 的 -50~200℃ 合理区间",
            metric=R.Metric.TEMPERATURE,
            expect_flag="SUSPECT",
            expect_reason_hint="区间",
            target="device",
            register_name="TEMPERATURE",
            register_value=5120,
        ),
        FaultScenario(
            key="status_illegal",
            label="状态码非法",
            desc="运行状态上报 99，而 MES 只认 0~10（0停机 1运行 2故障）",
            metric=R.Metric.STATUS,
            expect_flag="SUSPECT",
            expect_reason_hint="区间",
            target="device",
            register_name="RUN_STATUS",
            register_value=99,
        ),
        FaultScenario(
            key="sensor_fault",
            label="传感器故障",
            desc="故障码置为哨兵值 0xFFFF，网关识别后上报不可解析的标记串",
            metric=R.Metric.TEMPERATURE,
            expect_flag="BAD",
            expect_reason_hint="解析",
            target="collector",
            raw_payload="####",
        ),
        FaultScenario(
            key="garbage_value",
            label="乱码上报",
            desc="上报值混入非数字字符，无法解析成数值",
            metric=R.Metric.OUTPUT,
            expect_flag="BAD",
            expect_reason_hint="解析",
            target="collector",
            raw_payload="12x3",
        ),
        FaultScenario(
            key="output_over_limit",
            label="产量超上限",
            desc="上报产量 1000001，超出 MES 的 0~1000000 区间（16 位寄存器装不下，只能在这一层造）",
            metric=R.Metric.OUTPUT,
            expect_flag="SUSPECT",
            expect_reason_hint="区间",
            target="collector",
            raw_payload="1000001",
        ),
        FaultScenario(
            key="clock_drift",
            label="设备时钟漂移",
            desc="采集时间比真实时间超前 2 小时，会让按天统计把数据分错组",
            metric=R.Metric.OUTPUT,
            expect_flag="SUSPECT",
            expect_reason_hint="时间",
            target="collector",
            clock_offset_hours=2.0,
        ),
    )
}


@dataclass
class FaultInjector:
    """异常注入器：负责应用与恢复。

    设备侧的注入会改寄存器并把原值记下来，恢复时写回；
    采集侧的注入只影响下一次上报的原始串，不落任何状态。
    """

    device: DeviceSimulator
    active: str | None = None
    _saved: dict[int, int] = field(default_factory=dict)

    # ------------------------------------------------------------------ 查询

    @property
    def scenario(self) -> FaultScenario | None:
        return SCENARIOS.get(self.active) if self.active else None

    def raw_override(self, metric: R.Metric) -> str | None:
        """采集器上报前调用：若当前场景要覆盖该指标的原始串，返回覆盖值。"""
        sc = self.scenario
        if sc is None or sc.target != "collector" or sc.metric != metric:
            return None
        return sc.raw_payload

    def clock_offset(self) -> float:
        """采集器上报前调用：返回采集时间需要偏移的小时数。"""
        sc = self.scenario
        if sc is None or sc.clock_offset_hours is None:
            return 0.0
        return sc.clock_offset_hours

    def collect_time(self, now: datetime | None = None) -> datetime:
        return (now or datetime.now()) + timedelta(hours=self.clock_offset())

    # ------------------------------------------------------------------ 应用

    def inject(self, key: str) -> FaultScenario:
        """注入指定场景。重复注入会先恢复上一次，避免叠加出无法解释的状态。"""
        if key not in SCENARIOS:
            raise KeyError(f"未知异常场景 {key!r}，可选：{sorted(SCENARIOS)}")

        if self.active:
            self.restore()

        sc = SCENARIOS[key]
        if sc.target == "device" and sc.register_name is not None:
            addr = R.address_of(sc.register_name)
            self._saved[addr] = self.device.register_block[addr]
            self.device.register_block[addr] = sc.register_value or 0
            log.info("已注入设备侧异常：%s（%s = %s）", sc.label, sc.register_name, sc.register_value)
        else:
            log.info("已注入采集侧异常：%s（原始串 = %r）", sc.label, sc.raw_payload)

        self.active = key
        return sc

    def restore(self) -> None:
        """恢复设备侧被改动的寄存器。"""
        for addr, value in self._saved.items():
            self.device.register_block[addr] = value
        if self._saved:
            log.info("已恢复 %s 个寄存器原值", len(self._saved))
        self._saved.clear()
        if self.active:
            log.info("已撤销异常场景：%s", self.active)
        self.active = None

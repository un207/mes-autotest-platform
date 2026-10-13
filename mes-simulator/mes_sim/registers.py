"""设备寄存器点表 —— 地址到业务含义的唯一映射来源。

为什么把点表单独成文件：Modbus 只有"地址→16 位整数"，没有语义。
点表是把整数翻译成业务含义的那层，服务端（写值）和采集端（读值）都必须用它，
否则两边各写一份映射，迟早对不上。

一个工业常识体现在 `scale`：Modbus 保持寄存器是 16 位整数，存不了浮点。
现场惯例是把工程值乘以一个倍数存整数（温度 25.5℃ 存 255，即 scale=0.1）。
采集端再除回来。这不是偷懒，是协议本身的限制决定的。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Metric(str, Enum):
    """对应 MES 数采接口的指标枚举（值必须与 Java 端 MetricType 一致）。"""

    OUTPUT = "OUTPUT"
    STATUS = "STATUS"
    TEMPERATURE = "TEMPERATURE"


# 传感器的"故障哨兵值"。现场设备无法上报 NaN，惯例是用一个不可能的极值表示无效，
# 由网关识别后转成可读的原始串上报。65535 是 16 位无符号的最大值，正常工况不可能达到。
SENSOR_FAULT_SENTINEL = 0xFFFF


@dataclass(frozen=True)
class RegisterPoint:
    """一个寄存器点位。"""

    address: int
    name: str
    label: str
    metric: Metric | None
    unit: str
    scale: float
    desc: str
    cumulative: bool = False
    """是否为累计量。累计量只在数值变化时上报，瞬时量每轮上报。

    区分的依据是两类量的语义不同：累计产量未变化说明本周期没有新产出，
    重复上报同一个数没有信息量（轮询周期小于生产节拍时尤其明显，
    会让「累计产量」在列表里看起来反复跳动）；而温度、运行状态反映当前工况，
    即使与上一轮相同也应当有采样记录。
    """

    def to_engineering(self, raw: int) -> float:
        """寄存器整数 → 工程值（如 255 → 25.5）。"""
        return round(raw * self.scale, 4)

    def to_raw(self, engineering: float) -> int:
        """工程值 → 寄存器整数（如 25.5 → 255）。"""
        return int(round(engineering / self.scale))


# ---------------------------------------------------------------------------
# 点表：地址紧凑排布，前 3 个点位与 MES 的三种指标一一对应，
# 后几个是设备自身状态（不直接上报，供诊断与异常注入使用）。
# ---------------------------------------------------------------------------
POINTS: tuple[RegisterPoint, ...] = (
    RegisterPoint(0, "OUTPUT_COUNT", "累计产量", Metric.OUTPUT, "件", 1.0,
                  "设备开机以来的累计产出，随生产节拍递增", cumulative=True),
    RegisterPoint(1, "RUN_STATUS", "运行状态", Metric.STATUS, "", 1.0,
                  "0=停机 1=运行 2=故障（MES 侧合理区间为 0~10）"),
    RegisterPoint(2, "TEMPERATURE", "设备温度", Metric.TEMPERATURE, "℃", 0.1,
                  "主轴温度，寄存器存 0.1℃ 为单位的整数（255 = 25.5℃）"),
    RegisterPoint(3, "QUALIFIED_COUNT", "累计良品", None, "件", 1.0,
                  "设备自查的良品数，与产量配合可算设备侧直通率"),
    RegisterPoint(4, "DEFECTIVE_COUNT", "累计不良", None, "件", 1.0,
                  "设备自查的不良数"),
    RegisterPoint(5, "CYCLE_TIME", "生产节拍", None, "秒", 1.0,
                  "单件耗时，偏离基准说明设备状态异常"),
    RegisterPoint(6, "RUN_MINUTES", "运行时长", None, "分钟", 1.0,
                  "本次开机已运行时长"),
    RegisterPoint(7, "FAULT_CODE", "故障代码", None, "", 1.0,
                  f"0=无故障；{SENSOR_FAULT_SENTINEL}=传感器故障（触发脏数据场景）"),
)

# 按地址索引，供服务端按地址写入
BY_ADDRESS: dict[int, RegisterPoint] = {p.address: p for p in POINTS}
# 按名称索引，供代码可读地引用（不用记地址）
BY_NAME: dict[str, RegisterPoint] = {p.name: p for p in POINTS}

# 寄存器块大小（点位数量向上取整到 16 的倍数，符合工业惯例）
BLOCK_SIZE = 16


def address_of(name: str) -> int:
    """按点名取地址。写错点名的错误在这一层就暴露，比到处硬编码地址安全。"""
    try:
        return BY_NAME[name].address
    except KeyError as exc:
        raise KeyError(f"点表中没有名为 {name!r} 的点位，可选：{sorted(BY_NAME)}") from exc


# ---------------------------------------------------------------------------
# MES 侧的质量判定阈值（与 mes-platform 的 DeviceDataService.RANGES 对应）
# 放在这里是为了让模拟器能"知道自己造的数据会被判成什么"，便于自动校验。
# ---------------------------------------------------------------------------
MES_RANGES: dict[Metric, tuple[float, float]] = {
    Metric.OUTPUT: (0.0, 1_000_000.0),
    Metric.STATUS: (0.0, 10.0),
    Metric.TEMPERATURE: (-50.0, 200.0),
}

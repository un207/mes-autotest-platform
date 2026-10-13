"""采集器（Modbus 主站）—— 轮询设备寄存器并上报 MES。

工业链路的真实形态：设备只负责把数据放进寄存器，**不会主动推送**。
中间必须有一层采集程序（现场叫网关/SCADA）周期性地轮询设备，把数据转成业务系统能收的格式再上报。
这一段代码就是那层网关的最小实现，也是理解 OT/IT 边界的关键：

    设备（Modbus 从站）  ←轮询读取←  采集器  →HTTP 上报→  MES 数采接口
        寄存器内存                    格式转换

刻意不在采集器里做任何"业务判断"（比如温度是否超限）—— 那是 MES 的职责。
采集器的职责只有两件：把值读出来、如实报上去。这样质量判定逻辑只有一个归属地，
不会两边各判一套、结论还不一致。
"""

from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import dataclass, field
from datetime import datetime

import requests
from pymodbus.client import AsyncModbusTcpClient

from . import registers as R
from .faults import RANDOM_FAULT_POOL, FaultInjector

log = logging.getLogger(__name__)


@dataclass
class ReportResult:
    """一条上报的结果，含 MES 给出的质量判定。"""

    metric: R.Metric
    raw_value: str
    scene: str
    http_status: int
    code: int | None
    quality_flag: str | None
    quality_message: str | None
    device_data_id: int | None = None

    @property
    def ok(self) -> bool:
        return self.http_status == 200 and self.code == 0

    def describe(self) -> str:
        if not self.ok:
            return f"[{self.metric.value}] {self.raw_value!r} → 上报失败 HTTP={self.http_status} code={self.code}"
        flag = self.quality_flag or "?"
        mark = {"OK": "正常", "SUSPECT": "可疑", "BAD": "异常"}.get(flag, flag)
        extra = f"（{self.quality_message}）" if self.quality_message else ""
        return f"[{self.metric.value}] {self.raw_value!r} → {mark}{extra}"


@dataclass
class Collector:
    """把 Modbus 寄存器桥接到 MES 数采接口。"""

    device_code: str
    line_code: str
    modbus_host: str
    modbus_port: int
    unit_id: int
    mes_base_url: str
    injector: FaultInjector
    timeout: float = 8.0

    random_fault_rate: float = 0.0
    """随机故障概率（每指标每轮）。0 表示关闭，仅用于演示时制造可识别的脏数据。"""

    _client: AsyncModbusTcpClient | None = None
    _last_reported: dict[str, str] = field(default_factory=dict)
    """各指标最近一次上报的原始串，用于判断累计量是否变化。"""
    _rng: random.Random = field(default_factory=random.Random)

    # ------------------------------------------------------------------ 连接

    async def connect(self) -> bool:
        self._client = AsyncModbusTcpClient(self.modbus_host, port=self.modbus_port)
        await self._client.connect()
        return bool(self._client.connected)

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    # ------------------------------------------------------------------ 读寄存器

    async def read_points(self) -> dict[str, int] | None:
        """一次性把整块寄存器读回来（读所有点位只需一次请求，不必逐点读）。

        返回 None 表示读取失败（设备离线/异常响应）—— 调用方据此上报通信异常。
        """
        assert self._client is not None, "先调用 connect()"
        rr = await self._client.read_holding_registers(
            address=0, count=R.BLOCK_SIZE, device_id=self.unit_id
        )
        if rr.isError():
            log.warning("读取寄存器失败：%s", rr)
            return None
        return {p.name: rr.registers[p.address] for p in R.POINTS}

    # ------------------------------------------------------------------ 格式转换

    def to_raw_value(self, point: R.RegisterPoint, raw: int) -> str:
        """寄存器整数 → 上报串。

        温度按点表的 scale 转成工程值（255 → "25.5"），其余直接转十进制字符串。
        转换规则来自点表，不在这里写死，避免两处映射不一致。
        """
        if point.scale != 1.0:
            return str(point.to_engineering(raw))
        return str(raw)

    def build_payload(self, point: R.RegisterPoint, raw: int, now: datetime | None = None) -> dict:
        """组装一条上报报文。"""
        # 采集侧异常注入优先：现场故障时设备根本没有有效值，上报的是错误标记串
        override = self.injector.raw_override(point.metric)
        if override is not None:
            raw_value = override
        elif self.random_fault_rate and self._rng.random() < self.random_fault_rate:
            # 随机故障（演示用）：把正常值替换成现场常见的异常串，让把关逻辑可见
            raw_value = self._rng.choice(RANDOM_FAULT_POOL)
        else:
            raw_value = self.to_raw_value(point, raw)

        return {
            "equipmentCode": self.device_code,
            "lineCode": self.line_code,
            "metric": point.metric.value,
            "rawValue": raw_value,
            "unit": point.unit or None,
            "collectTime": self.injector.collect_time(now).strftime("%Y-%m-%d %H:%M:%S"),
        }

    # ------------------------------------------------------------------ 上报

    async def report_once(self, scene: str = "") -> list[ReportResult]:
        """读一轮寄存器，上报需要上报的指标。

        两处刻意的设计：

        ① **累计量只在数值变化时上报。** 轮询周期（默认 3s）小于生产节拍（默认 6s）时，
           同一个累计产量会被连续读到两次并重复入库，列表里看起来像「产量在反复跳动」。
           累计量未变化说明本周期没有新产出，重复上报没有信息量。
           温度与运行状态是瞬时量，每轮照报 —— 它们同时充当设备心跳，
           因此累计量跳过不会让 MES 失去对设备在线状态的感知。

        ② **串行上报而非并发。** 同一轮的多条记录采集时间相同（接口的 collectTime
           是秒级精度），并发上报的完成顺序不确定，会造成入库 id 顺序随机、
           列表顺序在两次刷新之间跳变。串行上报使写入顺序与点表顺序一致。
        """
        points = await self.read_points()
        if points is None:
            # 设备读不到时如实上报通信错误，而不是跳过 —— 沉默的采集器比报错的更危险
            return await self._report_comm_failure(scene)

        payloads: list[dict] = []
        for point in R.POINTS:
            if point.metric is None:
                continue  # 设备自身状态点不上报

            current = self.to_raw_value(point, points[point.name])
            # 被注入故障时强制上报：否则「累计量未变化跳过」会把故障数据一起跳过
            if (point.cumulative
                    and self.injector.raw_override(point.metric) is None
                    and self._last_reported.get(point.metric.value) == current):
                continue
            self._last_reported[point.metric.value] = current
            payloads.append(self.build_payload(point, points[point.name]))

        if not payloads:
            return []

        results: list[ReportResult] = []
        for p in payloads:
            resp = await asyncio.to_thread(self._post, p)
            results.append(self._to_result(p["metric"], p["rawValue"], scene, resp))
        return results

    def fetch_last_counter(self, metric: R.Metric) -> int | None:
        """从 MES 查回该设备某指标最近一次的数值，用于重启后延续累计量。

        为什么需要：模拟器每次启动都会把累计产量从 0 重新计数，而现场设备的计数器
        通常掉电保持。若不延续，列表里会出现「昨天累计到 3，今天从 0 开始」的回落，
        看起来像数据错误。采集类应用查询失败不应阻断启动，因此失败仅告警并返回 None。
        """
        url = f"{self.mes_base_url.rstrip('/')}/api/device-data"
        try:
            resp = requests.get(
                url,
                params={
                    "equipmentCode": self.device_code,
                    "metric": metric.value,
                    "pageNum": 1,
                    "pageSize": 1,
                },
                timeout=self.timeout,
            )
            body = resp.json()
            records = (body.get("data") or {}).get("records") or []
            if not records:
                return None
            value = records[0].get("metricValue")
            return int(float(value)) if value is not None else None
        except (requests.RequestException, ValueError, TypeError) as exc:
            log.warning("读取历史累计值失败（累计量将从 0 开始）：%s", exc)
            return None

    async def _report_comm_failure(self, scene: str) -> list[ReportResult]:
        """设备通信失败时的上报：原始串用通信错误标记，让 MES 判为不可解析。"""
        payloads = [
            {
                "equipmentCode": self.device_code,
                "lineCode": self.line_code,
                "metric": metric.value,
                "rawValue": "COMM_ERR",
                "unit": None,
                "collectTime": self.injector.collect_time().strftime("%Y-%m-%d %H:%M:%S"),
            }
            for metric in (R.Metric.OUTPUT, R.Metric.STATUS, R.Metric.TEMPERATURE)
        ]
        responses = await asyncio.gather(
            *(asyncio.to_thread(self._post, p) for p in payloads)
        )
        return [
            self._to_result(p["metric"], p["rawValue"], scene, resp)
            for p, resp in zip(payloads, responses)
        ]

    def _post(self, payload: dict) -> tuple[int, dict | None]:
        """同步 POST（在线程里跑，避免阻塞事件循环）。"""
        url = f"{self.mes_base_url.rstrip('/')}/api/device-data"
        try:
            resp = requests.post(url, json=payload, timeout=self.timeout)
            try:
                return resp.status_code, resp.json()
            except ValueError:
                return resp.status_code, None
        except requests.RequestException as exc:
            log.warning("上报失败 %s：%s", url, exc)
            return 0, None

    @staticmethod
    def _to_result(metric: R.Metric, raw: str, scene: str, resp: tuple[int, dict | None]) -> ReportResult:
        status, body = resp
        if body and isinstance(body, dict):
            data = body.get("data") or {}
            return ReportResult(
                metric=R.Metric(metric),
                raw_value=raw,
                scene=scene,
                http_status=status,
                code=body.get("code"),
                quality_flag=data.get("qualityFlag"),
                quality_message=data.get("qualityMessage"),
                device_data_id=data.get("id"),
            )
        return ReportResult(
            metric=R.Metric(metric), raw_value=raw, scene=scene,
            http_status=status, code=None, quality_flag=None, quality_message=None,
        )

    # ------------------------------------------------------------------ 便捷

    async def report_single(self, metric: R.Metric, raw_override: str | None = None,
                            scene: str = "") -> ReportResult:
        """只上报一个指标（用于定向验证某个异常场景）。"""
        point = next(p for p in R.POINTS if p.metric == metric)
        points = await self.read_points()
        raw = points[point.name] if points else 0
        payload = self.build_payload(point, raw)
        if raw_override is not None:
            payload["rawValue"] = raw_override
        status, body = await asyncio.to_thread(self._post, payload)
        return self._to_result(metric, payload["rawValue"], scene, (status, body))

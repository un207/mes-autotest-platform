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
from dataclasses import dataclass
from datetime import datetime

import requests
from pymodbus.client import AsyncModbusTcpClient

from . import registers as R
from .faults import FaultInjector

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

    _client: AsyncModbusTcpClient | None = None

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
        raw_value = override if override is not None else self.to_raw_value(point, raw)

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
        """读一轮寄存器，把三种指标各上报一条。"""
        points = await self.read_points()
        if points is None:
            # 设备读不到时如实上报通信错误，而不是跳过 —— 沉默的采集器比报错的更危险
            return await self._report_comm_failure(scene)

        payloads: list[dict] = []
        for point in R.POINTS:
            if point.metric is None:
                continue  # 设备自身状态点不上报
            payloads.append(self.build_payload(point, points[point.name]))

        responses = await asyncio.gather(
            *(asyncio.to_thread(self._post, p) for p in payloads)
        )
        return [
            self._to_result(p["metric"], p["rawValue"], scene, resp)
            for p, resp in zip(payloads, responses)
        ]

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

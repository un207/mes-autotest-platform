"""Modbus TCP 服务端 —— 把设备模拟成一台真实的 Modbus 从站。

pymodbus 3.16 的选型说明（这是本项目里唯一需要"绕"一下的地方，理由记录在此）：

  3.16 把 datastore 层重构了：旧 API（ModbusDeviceContext / ModbusSequentialDataBlock）
  官方已标记弃用、v4 将移除；新 API（SimData/SimDevice）是官方方向，但它是为**静态仿真配置**
  设计的 —— SimData 的值在构建期确定，没有公开的运行时写入接口。而设备模拟器必须能
  在运行中改寄存器（产量要增长、温度要波动），所以只能借助 SimRuntime 的内存块。

  SimRuntime 内部结构：`runtime.block["x"] = (start_address, count, registers, flags)`，
  其中 registers 是**列表引用**，服务端读请求时直接读这个列表。因此拿到该引用即可实时改值。
  这里只依赖这一个内部结构，并把它收在 `registers` 属性里 ——
  将来 pymodbus 升级若破坏它，只会坏这一处，且自检会立刻报出来。
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

from pymodbus.server import ModbusTcpServer
from pymodbus.simulator import SimData, SimDevice
from pymodbus.simulator.simdata import DataType

from . import registers as R

log = logging.getLogger(__name__)


@dataclass
class ModbusDeviceServer:
    """一台 Modbus TCP 从站（对应一台产线设备）。"""

    host: str = "127.0.0.1"
    port: int = 5020
    unit_id: int = 1
    """从站号。Modbus TCP 里靠它区分同一网关下的多台设备。"""

    _server: ModbusTcpServer | None = field(default=None, init=False, repr=False)
    _task: asyncio.Task | None = field(default=None, init=False, repr=False)
    registers: list[int] = field(default_factory=lambda: [0] * R.BLOCK_SIZE, init=False)
    """与 Modbus 服务端共享的寄存器内存。改它 = 改设备当前值。"""

    # ------------------------------------------------------------------ 启动

    def _build(self) -> None:
        """构建服务端，并取出共享的寄存器列表。"""
        initial = [0] * R.BLOCK_SIZE
        simdata = SimData(
            address=0,
            count=R.BLOCK_SIZE,
            values=list(initial),
            datatype=DataType.UINT16,
        )
        device = SimDevice(id=self.unit_id, simdata=simdata)
        self._server = ModbusTcpServer(device, address=(self.host, self.port))

        # 取出 SimRuntime 持有的那块内存（见模块开头的说明）
        core = self._server.context
        runtime = core.devices[self.unit_id]
        block = runtime.block
        key = "x" if "x" in block else "h"
        shared = block[key][2]

        # 注意：pymodbus 会把块扩到比请求更大的尺寸（实测请求 16 个、实际得到 257 个，
        # 应为内部对齐/填充）。所以这里只要求「不小于点表所需范围」，不要求相等。
        if not isinstance(shared, list) or len(shared) < R.BLOCK_SIZE:
            raise RuntimeError(
                "pymodbus 内部结构已变化，无法取得共享寄存器块"
                f"（拿到 {type(shared).__name__}，长度 "
                f"{len(shared) if hasattr(shared, '__len__') else '?'}，"
                f"至少需要 {R.BLOCK_SIZE}）。请检查 pymodbus 版本，"
                "或改回自建 Modbus 服务端实现。"
            )

        self.registers = shared
        log.info(
            "Modbus TCP 从站已构建 %s:%s unit=%s 寄存器块=%s 个（点表用 %s 个）",
            self.host, self.port, self.unit_id, len(shared), R.BLOCK_SIZE,
        )

    async def serve_forever(self) -> None:
        """启动并常驻。应在 asyncio 任务里运行。"""
        if self._server is None:
            self._build()
        assert self._server is not None
        await self._server.serve_forever()

    def start_background(self) -> asyncio.Task:
        """在后台起服务，返回任务句柄（用于控制循环里 await asyncio.gather）。"""
        self._task = asyncio.create_task(self.serve_forever(), name=f"modbus-{self.port}")
        return self._task

    # ------------------------------------------------------------------ 停止

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            except Exception as exc:  # noqa: BLE001 - 关停阶段的异常不该影响主流程
                log.debug("Modbus 服务端停止时出现异常（可忽略）：%s", exc)
            self._task = None
        self._server = None

    # ------------------------------------------------------------------ 自检

    async def self_check(self) -> tuple[bool, str]:
        """起服务后用真实客户端读一次，确认服务端真的可用。

        为什么要自检：服务端"看起来起来了"不等于客户端能读到数据 ——
        端口占用、unit_id 不匹配、寄存器块没挂上，都可能让服务假活。
        """
        from pymodbus.client import AsyncModbusTcpClient

        client = AsyncModbusTcpClient(self.host, port=self.port)
        try:
            await client.connect()
            if not client.connected:
                return False, f"客户端无法连接 {self.host}:{self.port}"

            # 先写一个可识别的值，再读回来，确认读写通路都通
            marker = 0x5A5A
            self.registers[0] = marker
            rr = await client.read_holding_registers(address=0, count=1, device_id=self.unit_id)
            if rr.isError():
                return False, f"读取返回错误：{rr}"
            if rr.registers[0] != marker:
                return False, f"回读值不符：期望 {marker}，实际 {rr.registers[0]}"
            return True, f"读写通路正常（回读 {marker}）"
        except Exception as exc:  # noqa: BLE001
            return False, f"{type(exc).__name__}: {exc}"
        finally:
            client.close()

"""M4 设备模拟器 —— 用 Modbus TCP 模拟产线设备，把数据送进 MES。

对外只需要三样东西：
    load_config()       读配置（支持环境变量覆盖）
    build_simulator()   组装「服务端 + 设备模型 + 异常注入器」
    Collector           采集上报器
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = ROOT / "config" / "simulator.yml"

__all__ = ["load_config", "build_simulator", "Collector", "DeviceSimulator", "DeviceProfile",
           "ModbusDeviceServer", "FaultInjector", "SCENARIOS", "ReportResult", "ROOT"]


def load_config(path: Path | None = None) -> dict[str, Any]:
    """读配置。敏感项与地址可用环境变量覆盖，便于 CI 与换机运行。

    支持覆盖：MES_BASE_URL / SIM_MODBUS_HOST / SIM_MODBUS_PORT / SIM_UNIT_ID /
             SIM_EQUIPMENT_CODE / SIM_LINE_CODE / SIM_INTERVAL
    """
    target = path or CONFIG_FILE
    if not target.exists():
        raise FileNotFoundError(f"配置文件不存在：{target}")

    with target.open(encoding="utf-8") as f:
        cfg: dict[str, Any] = yaml.safe_load(f) or {}

    modbus = dict(cfg.get("modbus", {}))
    modbus["host"] = os.getenv("SIM_MODBUS_HOST", modbus.get("host", "127.0.0.1"))
    modbus["port"] = int(os.getenv("SIM_MODBUS_PORT", modbus.get("port", 5020)))
    modbus["unit_id"] = int(os.getenv("SIM_UNIT_ID", modbus.get("unit_id", 1)))

    device = dict(cfg.get("device", {}))
    device["equipment_code"] = os.getenv("SIM_EQUIPMENT_CODE", device.get("equipment_code", "SIM-DEV-01"))
    device["line_code"] = os.getenv("SIM_LINE_CODE", device.get("line_code", "SIM-LINE-A"))

    collector = dict(cfg.get("collector", {}))
    collector["mes_base_url"] = os.getenv("MES_BASE_URL", collector.get("mes_base_url", "http://127.0.0.1:8080"))
    collector["interval_seconds"] = float(os.getenv("SIM_INTERVAL", collector.get("interval_seconds", 3.0)))

    runtime = dict(cfg.get("runtime", {}))

    return {"modbus": modbus, "device": device, "collector": collector, "runtime": runtime}


def build_simulator(cfg: dict[str, Any]):
    """按配置组装「Modbus 服务端 + 设备模型 + 异常注入器」。

    返回 (server, device, injector)。三者的连接关系：
      - server 先建，取出共享寄存器块
      - device 持有该寄存器块，tick 时写值
      - injector 持有 device，注入时直接改寄存器块

    注意顺序不能颠倒：寄存器块由 server 创建，device 必须后建才能拿到它。
    """
    from .device import DeviceProfile, DeviceSimulator
    from .faults import FaultInjector
    from .server import ModbusDeviceServer

    modbus_cfg, dev_cfg = cfg["modbus"], cfg["device"]

    server = ModbusDeviceServer(
        host=modbus_cfg["host"],
        port=modbus_cfg["port"],
        unit_id=modbus_cfg["unit_id"],
    )
    # 先触发构建，拿到共享寄存器块
    server._build()  # noqa: SLF001 - 有意提前构建，供 device 共享内存

    profile = DeviceProfile(
        cycle_seconds=float(dev_cfg.get("cycle_seconds", 6.0)),
        base_temperature=float(dev_cfg.get("base_temperature", 24.0)),
        temperature_drift=float(dev_cfg.get("temperature_drift", 0.6)),
        temperature_limit=float(dev_cfg.get("temperature_limit", 78.0)),
        defect_rate=float(dev_cfg.get("defect_rate", 0.03)),
        startup_minutes=int(dev_cfg.get("startup_minutes", 0)),
    )
    device = DeviceSimulator(
        equipment_code=dev_cfg["equipment_code"],
        line_code=dev_cfg["line_code"],
        register_block=server.registers,
        profile=profile,
    )
    injector = FaultInjector(device=device)
    return server, device, injector


from .collector import Collector, ReportResult  # noqa: E402
from .device import DeviceProfile, DeviceSimulator  # noqa: E402
from .faults import SCENARIOS, FaultInjector  # noqa: E402
from .server import ModbusDeviceServer  # noqa: E402

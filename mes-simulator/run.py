"""运行设备模拟器：起 Modbus 从站 → 设备逻辑持续运转 → 采集器周期上报 MES。

用法：
    python run.py                          # 正常运行（起设备 + 采集，持续上报）
    python run.py --duration 30            # 跑 30 秒后自动退出（便于脚本化验证）
    python run.py --fault temp_overheat    # 注入指定异常场景
    python run.py --list-faults            # 列出全部可用异常场景
    python run.py --self-check             # 只做自检（验证 Modbus 通路，不连 MES）
    python run.py --no-collect             # 只跑设备，不上报（观察寄存器变化）
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import sys

from mes_sim import SCENARIOS, Collector, build_simulator, load_config

log = logging.getLogger("simulator")


def setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s [%(levelname)-7s] %(name)s - %(message)s",
        datefmt="%H:%M:%S",
    )
    # pymodbus 内部日志在 INFO 级别很吵，压到 WARNING
    logging.getLogger("pymodbus").setLevel(logging.WARNING)


async def device_loop(device, tick_seconds: float, log_every: int, stop: asyncio.Event) -> None:
    """设备心跳：按步长推进设备逻辑。"""
    ticks = 0
    while not stop.is_set():
        device.tick(tick_seconds)
        ticks += 1
        if log_every and ticks % log_every == 0:
            snap = device.snapshot()
            log.info(
                "设备状态 产量=%s 良品=%s 不良=%s 温度=%.1f℃ 状态=%s 已运行=%s分钟",
                snap["output"], snap["qualified"], snap["defective"],
                snap["temperature"], snap["statusLabel"], snap["runMinutes"],
            )
        try:
            await asyncio.wait_for(stop.wait(), timeout=tick_seconds)
        except asyncio.TimeoutError:
            pass


async def collect_loop(collector: Collector, interval: float, stop: asyncio.Event) -> None:
    """采集循环：轮询寄存器并上报 MES。"""
    rounds = 0
    while not stop.is_set():
        rounds += 1
        scene = ""
        results = await collector.report_once(scene=scene)
        for r in results:
            level = logging.INFO if r.ok else logging.WARNING
            log.log(level, "第 %s 轮上报 %s", rounds, r.describe())

        # 统计本轮判定分布，异常时给出提示（让人一眼看到"脏数据被识别了"）
        abnormal = [r for r in results if r.quality_flag and r.quality_flag != "OK"]
        if abnormal:
            log.warning("本轮有 %s 条被判为异常/可疑 —— 这些数据会进入 MES 的异常清单待排查", len(abnormal))

        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
        except asyncio.TimeoutError:
            pass


async def run_normal(args) -> int:
    cfg = load_config()
    server, device, injector = build_simulator(cfg)

    # ---- 自检：确认 Modbus 读写通路是通的，别等采集时才发现在空转 ----
    log.info("启动 Modbus 从站 %s:%s（unit=%s）",
             cfg["modbus"]["host"], cfg["modbus"]["port"], cfg["modbus"]["unit_id"])
    server_task = server.start_background()
    await asyncio.sleep(0.5)

    ok, detail = await server.self_check()
    if not ok:
        log.error("Modbus 服务端自检失败：%s", detail)
        await server.stop()
        return 2
    log.info("Modbus 服务端自检通过：%s", detail)

    # ---- 设备开机 ----
    if args.fault:
        sc = injector.inject(args.fault)
        log.warning("已按参数注入异常场景：%s —— %s", sc.label, sc.desc)
    device.start()
    log.info("设备已开机：%s", device.snapshot())

    collector = Collector(
        device_code=device.equipment_code,
        line_code=device.line_code,
        modbus_host=cfg["modbus"]["host"],
        modbus_port=cfg["modbus"]["port"],
        unit_id=cfg["modbus"]["unit_id"],
        mes_base_url=cfg["collector"]["mes_base_url"],
        injector=injector,
        timeout=float(cfg["collector"]["timeout"]),
    )

    stop = asyncio.Event()
    _install_signal_handlers(stop)

    tasks: list[asyncio.Task] = [server_task]
    tasks.append(asyncio.create_task(
        device_loop(device, float(cfg["runtime"]["tick_seconds"]),
                    int(cfg["runtime"]["log_every_ticks"]), stop),
        name="device-loop",
    ))

    if not args.no_collect:
        if not await collector.connect():
            log.error("采集器无法连接 Modbus 从站")
            stop.set()
            await server.stop()
            return 2
        log.info("采集器已连接，轮询周期 %ss，上报目标 %s",
                 cfg["collector"]["interval_seconds"], cfg["collector"]["mes_base_url"])
        tasks.append(asyncio.create_task(
            collect_loop(collector, float(cfg["collector"]["interval_seconds"]), stop),
            name="collect-loop",
        ))

    # ---- 运行到退出条件 ----
    try:
        if args.duration:
            log.info("将运行 %s 秒后自动退出", args.duration)
            try:
                await asyncio.wait_for(stop.wait(), timeout=float(args.duration))
            except asyncio.TimeoutError:
                log.info("运行时长到达，准备退出")
        else:
            log.info("模拟器运行中，按 Ctrl+C 停止")
            await stop.wait()
    finally:
        stop.set()
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        collector.close()
        await server.stop()
        log.info("已停止。设备最终状态：%s", device.snapshot())
    return 0


def _install_signal_handlers(stop: asyncio.Event) -> None:
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except (NotImplementedError, AttributeError):
            # Windows 的事件循环对信号支持有限，退回到 KeyboardInterrupt
            pass


async def run_self_check() -> int:
    """只验证 Modbus 通路，不碰 MES。适合在没起 MES 时确认模拟器本身没问题。"""
    cfg = load_config()
    server, device, injector = build_simulator(cfg)
    log.info("自检：启动 Modbus 从站 %s:%s", cfg["modbus"]["host"], cfg["modbus"]["port"])
    server_task = server.start_background()
    await asyncio.sleep(0.5)
    try:
        ok, detail = await server.self_check()
        if not ok:
            log.error("自检失败：%s", detail)
            return 2
        log.info("读写通路：%s", detail)

        # 再验证设备逻辑：推进若干 tick，确认产量确实在涨
        device.start()
        before = device.read_raw("OUTPUT_COUNT")
        for _ in range(24):
            device.tick(1.0)
        after = device.read_raw("OUTPUT_COUNT")
        if after <= before:
            log.error("设备逻辑异常：推进 24 秒后产量没增长（%s → %s）", before, after)
            return 2
        log.info("设备逻辑正常：推进 24 秒，产量 %s → %s，温度 %.1f℃",
                 before, after, device.snapshot()["temperature"])

        # 验证异常注入能否真的改到寄存器
        sc = injector.inject("temp_overheat")
        injected = device.read_raw("TEMPERATURE")
        injector.restore()
        restored = device.read_raw("TEMPERATURE")
        if injected != 5120 or restored == injected:
            log.error("异常注入未按预期工作：注入后=%s 恢复后=%s", injected, restored)
            return 2
        log.info("异常注入正常：%s 注入后寄存器=%s，恢复后=%s", sc.label, injected, restored)

        log.info("自检全部通过")
        return 0
    finally:
        server_task.cancel()
        await asyncio.gather(server_task, return_exceptions=True)
        await server.stop()


def main() -> int:
    parser = argparse.ArgumentParser(description="MES 设备模拟器（Modbus TCP）")
    parser.add_argument("--fault", help="注入指定异常场景（见 --list-faults）")
    parser.add_argument("--list-faults", action="store_true", help="列出全部异常场景")
    parser.add_argument("--self-check", action="store_true", help="只做自检，不连 MES")
    parser.add_argument("--duration", type=float, help="运行多少秒后自动退出")
    parser.add_argument("--no-collect", action="store_true", help="只跑设备，不上报 MES")
    parser.add_argument("-v", "--verbose", action="store_true", help="调试日志")
    args = parser.parse_args()

    setup_logging(args.verbose)

    if args.list_faults:
        print("可注入的异常场景：\n")
        for sc in SCENARIOS.values():
            where = "设备侧（改寄存器）" if sc.target == "device" else "采集侧（改上报串）"
            print(f"  {sc.key:<20} {sc.label}")
            print(f"      注入层：{where}｜影响指标：{sc.metric.value}｜预期 MES 判定：{sc.expect_flag}")
            print(f"      说明：{sc.desc}\n")
        return 0

    try:
        if args.self_check:
            return asyncio.run(run_self_check())
        return asyncio.run(run_normal(args))
    except KeyboardInterrupt:
        print("\n已中断")
        return 130


if __name__ == "__main__":
    sys.exit(main())

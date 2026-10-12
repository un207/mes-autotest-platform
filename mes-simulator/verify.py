"""M4 端到端验证：证明「模拟器造的异常数据，MES 真的能识别出来」。

为什么单独做这个脚本：光看模拟器能起服务、能上报成功，并不能说明 MES 的质量把关有效 ——
很可能所有数据都被判 OK（那就等于把关形同虚设），也可能所有数据都被判异常（把关过严）。

所以要三种情况都验：
  ① 基线：无故障时上报，三种指标都应判 OK
  ② 异常：逐个注入 6 个场景，各自应判出预期的标记（BAD / SUSPECT）与原因
  ③ 恢复：撤销注入后再上报，应回到 OK  —— 证明注入不影响后续，不是"一次性污染"

用法：
    python verify.py                 # 跑完整验证
    python verify.py --list          # 只列出待验证的场景
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

import requests

from mes_sim import SCENARIOS, Collector, build_simulator, load_config
from mes_sim import registers as R

log = logging.getLogger("verify")

FLAG_LABEL = {"OK": "正常", "SUSPECT": "可疑", "BAD": "异常"}


class Checker:
    """收集验证结果并输出报告。"""

    def __init__(self) -> None:
        self.rows: list[tuple[str, bool, str]] = []

    def check(self, name: str, passed: bool, detail: str) -> None:
        self.rows.append((name, passed, detail))
        mark = "PASS" if passed else "FAIL"
        print(f"  {mark}  {name}\n        {detail}", flush=True)

    @property
    def failed(self) -> int:
        return sum(1 for _, ok, _ in self.rows if not ok)

    def summary(self) -> str:
        total = len(self.rows)
        passed = total - self.failed
        bar = "=" * 60
        lines = [bar, f"  验证结果：{passed}/{total} 通过"]
        if self.failed:
            lines.append("  失败项：")
            lines.extend(f"    - {n}：{d}" for n, ok, d in self.rows if not ok)
        lines.append(bar)
        return "\n".join(lines)


def mes_reachable(base_url: str) -> tuple[bool, str]:
    """确认 MES 可达且数据库连通。"""
    try:
        resp = requests.get(f"{base_url.rstrip('/')}/api/ready", timeout=8)
        body = resp.json()
        data = body.get("data") or {}
        if body.get("code") == 0 and data.get("database") == "UP":
            return True, f"MES 就绪，数据库 {data.get('dbProduct')}"
        return False, f"MES 响应异常：code={body.get('code')} database={data.get('database')}"
    except requests.RequestException as exc:
        return False, f"无法连接 {base_url}：{exc}"


async def run_verify(args) -> int:
    cfg = load_config()
    base_url = cfg["collector"]["mes_base_url"]

    print("=" * 60)
    print("  M4 端到端验证：模拟器 → Modbus → 采集器 → MES 数采接口")
    print("=" * 60)

    # ---- 前置：MES 必须可达 ----
    ok, detail = mes_reachable(base_url)
    print(f"\n[前置] {detail}")
    if not ok:
        print(
            "\n  MES 不可达，无法验证。请先启动被测系统（数据会写入它连的那个库）：\n"
            "    cd ../mes-platform\n"
            "    unset SERVER__PORT SERVER__HOST\n"
            '    export JAVA_HOME="C:/Users/Administrator/.jdks/temurin-17.0.20.1"\n'
            "    mvn spring-boot:run\n"
        )
        return 2

    checker = Checker()
    server, device, injector = build_simulator(cfg)
    server_task = server.start_background()
    await asyncio.sleep(0.5)

    collector = Collector(
        device_code=device.equipment_code,
        line_code=device.line_code,
        modbus_host=cfg["modbus"]["host"],
        modbus_port=cfg["modbus"]["port"],
        unit_id=cfg["modbus"]["unit_id"],
        mes_base_url=base_url,
        injector=injector,
        timeout=float(cfg["collector"]["timeout"]),
    )

    try:
        # ---- 0. 通道自检 ----
        print("\n[0] Modbus 通道自检")
        ok, detail = await server.self_check()
        checker.check("Modbus 读写通路", ok, detail)
        if not ok:
            return 2

        if not await collector.connect():
            checker.check("采集器连接 Modbus 从站", False, "连接失败")
            return 2
        device.start()

        # 让设备跑一会儿，产出一些真实数据（否则产量为 0，看不出"正常"的样子）
        for _ in range(20):
            device.tick(1.0)
        snap = device.snapshot()
        print(f"  设备已运行：产量 {snap['output']}、良品 {snap['qualified']}、"
              f"温度 {snap['temperature']}℃ —— {snap['statusLabel']}")

        # ---- 1. 基线：正常数据应判 OK ----
        print("\n[1] 基线验证：无故障时三种指标都应判「正常」")
        injector.restore()
        results = await collector.report_once(scene="baseline")
        for r in results:
            checker.check(
                f"基线 {r.metric.value}",
                r.ok and r.quality_flag == "OK",
                f"上报 {r.raw_value!r} → 判定 {FLAG_LABEL.get(r.quality_flag or '', r.quality_flag)}"
                f"（期望 正常）",
            )

        # ---- 2. 异常场景逐个验证 ----
        print("\n[2] 异常注入验证：每个场景都应被 MES 识别")
        for key, sc in SCENARIOS.items():
            injector.inject(key)
            try:
                res = await collector.report_single(sc.metric, scene=key)
            finally:
                injector.restore()

            flag = res.quality_flag or "?"
            flag_ok = flag == sc.expect_flag
            reason_ok = sc.expect_reason_hint in (res.quality_message or "")
            where = "设备侧" if sc.target == "device" else "采集侧"
            passed = res.ok and flag_ok and reason_ok

            detail = (
                f"{where}注入「{sc.label}」→ 上报 {res.raw_value!r} "
                f"→ 判定 {FLAG_LABEL.get(flag, flag)}"
            )
            if res.quality_message:
                detail += f"，原因：{res.quality_message}"
            if not flag_ok:
                detail += f"（期望 {FLAG_LABEL.get(sc.expect_flag, sc.expect_flag)}）"
            if res.ok and flag_ok and not reason_ok:
                detail += f"（判定对但原因没提到「{sc.expect_reason_hint}」）"
            if not res.ok:
                detail += f"（上报本身失败 HTTP={res.http_status} code={res.code}）"

            checker.check(f"异常场景 {key}", passed, detail)

        # ---- 3. 恢复后应回到正常 ----
        print("\n[3] 恢复验证：撤销注入后应回到「正常」")
        results = await collector.report_once(scene="after-restore")
        for r in results:
            checker.check(
                f"恢复后 {r.metric.value}",
                r.ok and r.quality_flag == "OK",
                f"上报 {r.raw_value!r} → 判定 {FLAG_LABEL.get(r.quality_flag or '', r.quality_flag)}"
                f"（期望 正常）",
            )

        # ---- 4. 异常清单可捞取 ----
        print("\n[4] 异常数据可追溯：MES 的异常清单应能捞到本轮注入的数据")
        try:
            resp = requests.get(
                f"{base_url.rstrip('/')}/api/device-data/abnormal",
                params={"limit": 200}, timeout=8,
            )
            rows = (resp.json().get("data") or [])
            mine = [r for r in rows if r.get("equipmentCode") == device.equipment_code]
            checker.check(
                "异常清单",
                len(mine) >= len(SCENARIOS),
                f"该设备共有 {len(mine)} 条非正常记录（本轮注入 {len(SCENARIOS)} 个场景，"
                f"期望至少这么多）",
            )
            if mine:
                sample = mine[0]
                print(f"        样例：{sample.get('metric')} {sample.get('rawValue')!r} "
                      f"→ {sample.get('qualityFlag')}（{sample.get('qualityMessage')}）")
        except requests.RequestException as exc:
            checker.check("异常清单", False, f"查询失败：{exc}")

        print("\n" + checker.summary())
        return 0 if checker.failed == 0 else 1

    finally:
        collector.close()
        server_task.cancel()
        await asyncio.gather(server_task, return_exceptions=True)
        await server.stop()
        # 恢复设备侧寄存器，别把异常状态留在内存里给人误解
        injector.restore()


def main() -> int:
    parser = argparse.ArgumentParser(description="M4 端到端验证")
    parser.add_argument("--list", action="store_true", help="列出待验证的异常场景")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%H:%M:%S",
    )

    if args.list:
        for sc in SCENARIOS.values():
            print(f"{sc.key:<20} {sc.label:<10} {sc.metric.value:<12} 期望={sc.expect_flag}")
        return 0

    return asyncio.run(run_verify(args))


if __name__ == "__main__":
    sys.exit(main())

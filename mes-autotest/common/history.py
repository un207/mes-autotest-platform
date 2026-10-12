"""执行历史留档 —— 通过率趋势的数据源。

设计取舍：历史记录必须能**跨机器累积**（CI 上跑一轮、本机跑一轮，趋势要连得上），
所以落成一个按行追加的 JSONL 文件，进版本控制（`history/api-test-history.jsonl`）。
与 `reports/` 严格分开：reports/ 是一次性产物（随时可删重生成），history/ 是累积资产。

不上数据库的理由：这是给人看的趋势，不是要查询的业务数据。JSONL 直接可读、可 diff、
出问题能手改，比引一个库划算。同理趋势图用手写 SVG，不引图表库。
"""

from __future__ import annotations

import json
import os
import socket
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
HISTORY_DIR = ROOT / "history"
HISTORY_FILE = HISTORY_DIR / "api-test-history.jsonl"

# 展示统一用北京时间：CI runner 在 UTC、开发者本机在 UTC+8，
# 若各自记本地时间，同一份趋势里时间会忽早忽晚，排序与阅读都会错乱。
DISPLAY_TZ = timezone(timedelta(hours=8))


def history_file() -> Path:
    """历史文件路径。可用 MES_HISTORY_FILE 覆盖（便于隔离测试或多环境分开累积）。"""
    override = os.getenv("MES_HISTORY_FILE")
    return Path(override) if override else HISTORY_FILE


def to_display(instant: datetime) -> str:
    """把任意时区的时刻转成北京时间字符串（用于展示）。"""
    return instant.astimezone(DISPLAY_TZ).strftime("%Y-%m-%d %H:%M:%S")


def sort_key(record: dict[str, Any]) -> float:
    """排序键（epoch 秒）。

    优先用带时区的 `ts` 字段，这样跨时区（本机 UTC+8 / CI UTC）也能正确排序；
    没有 `ts` 的旧记录退化为按 `time` 解析并**假定为北京时间** —— 这批记录都是
    本机产生的，本机即 UTC+8，所以这个假定是准确的。
    """
    raw_ts = record.get("ts")
    if raw_ts:
        try:
            return datetime.fromisoformat(raw_ts).timestamp()
        except (ValueError, TypeError):
            pass

    raw_time = record.get("time", "")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(raw_time, fmt).replace(tzinfo=DISPLAY_TZ).timestamp()
        except ValueError:
            continue
    return 0.0


def append_run(
    total: int,
    passed: int,
    failed: int,
    error: int,
    skipped: int,
    duration: float,
    *,
    run_id: str = "",
    label: str = "",
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """追加一轮执行结果，返回写入的记录。

    幂等保护：若同一 run_id 已存在则不重复追加（重跑报告渲染时不会污染趋势）。
    """
    target = history_file()
    target.parent.mkdir(parents=True, exist_ok=True)

    now = datetime.now().astimezone()
    record: dict[str, Any] = {
        # ts 带时区偏移，是排序与跨时区比较的依据；time 是供人阅读的北京时间
        "ts": now.isoformat(timespec="seconds"),
        "time": to_display(now),
        "run_id": run_id or now.strftime("%Y%m%d%H%M%S"),
        # label 用于区分执行来源，趋势图上要能看出「这轮是 CI 跑的还是在本地跑的」
        "label": label or os.getenv("MES_RUN_LABEL", "local"),
        "host": socket.gethostname(),
        "total": total,
        "passed": passed,
        "failed": failed,
        "error": error,
        "skipped": skipped,
        "duration": round(duration, 3),
        "pass_rate": round(passed / total * 100, 2) if total else 0.0,
    }
    if meta:
        record["meta"] = meta

    if _exists(record["run_id"]):
        return record

    with target.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def _exists(run_id: str) -> bool:
    target = history_file()
    if not target.exists():
        return False
    with target.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                if json.loads(line).get("run_id") == run_id:
                    return True
            except json.JSONDecodeError:
                continue
    return False


def load_history(limit: int = 0) -> list[dict[str, Any]]:
    """按时间顺序读取历史记录。limit>0 时只取最近 N 轮。"""
    target = history_file()
    if not target.exists():
        return []

    records: list[dict[str, Any]] = []
    with target.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                # 单行损坏不该让整个趋势挂掉，跳过即可
                continue

    records.sort(key=sort_key)
    return records[-limit:] if limit > 0 else records


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    """汇总统计，给趋势页与终端摘要共用。

    注意：返回值必须**始终包含全部键**（空历史时用零值占位）——
    调用方直接按 key 取值，缺键会让「首次使用」这条最常见的路径直接崩掉。
    """
    if not records:
        return {
            "runs": 0,
            "latest": None,
            "best": None,
            "worst": None,
            "avg_pass_rate": 0.0,
            "streak": 0,
            "total_cases_latest": 0,
        }

    rates = [r.get("pass_rate", 0.0) for r in records]
    latest = records[-1]

    # 连续全绿轮次（从最新往回数）
    streak = 0
    for r in reversed(records):
        if r.get("failed", 0) == 0 and r.get("error", 0) == 0:
            streak += 1
        else:
            break

    return {
        "runs": len(records),
        "latest": latest,
        "best": max(records, key=lambda r: r.get("pass_rate", 0.0)),
        "worst": min(records, key=lambda r: r.get("pass_rate", 0.0)),
        "avg_pass_rate": round(sum(rates) / len(rates), 2),
        "streak": streak,
        "total_cases_latest": latest.get("total", 0),
    }

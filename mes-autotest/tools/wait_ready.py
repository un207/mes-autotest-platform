"""等待被测系统就绪。

CI 与本地都用它 —— 不要用 `sleep 30` 这种写法：服务起得慢就假失败，起得快就白等，
而且失败时看不出到底卡在哪儿。这里明确轮询就绪接口，超时后给出可操作的排查指引。

用法：
    python tools/wait_ready.py
    python tools/wait_ready.py --url http://127.0.0.1:8080 --timeout 180
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request


def probe(url: str, timeout: float = 3.0) -> tuple[bool, str]:
    """探一次就绪接口，返回 (是否就绪, 描述)。"""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return False, f"响应不是 JSON：{raw[:120]}"

        data = payload.get("data") or {}
        db = data.get("database", "?")
        if payload.get("code") == 0 and data.get("status") == "UP":
            return True, f"服务就绪，数据库={db}（{data.get('dbProduct', '?')}）"
        return False, f"服务已响应但未就绪：code={payload.get('code')} database={db}"
    except urllib.error.HTTPError as exc:
        # 就绪检查在数据库不通时返回 503 —— 这时服务进程已经起来了，只是下游没通
        return False, f"HTTP {exc.code}（服务在跑，但依赖未就绪）"
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return False, f"连接失败：{exc.__class__.__name__}"


def main() -> int:
    parser = argparse.ArgumentParser(description="等待 MES 服务就绪")
    parser.add_argument("--url", default="http://127.0.0.1:8080")
    parser.add_argument("--timeout", type=int, default=150, help="总超时秒数")
    parser.add_argument("--interval", type=float, default=2.0, help="轮询间隔秒数")
    args = parser.parse_args()

    endpoint = args.url.rstrip("/") + "/api/ready"
    deadline = time.time() + args.timeout
    attempt = 0
    last = ""

    while time.time() < deadline:
        attempt += 1
        ready, detail = probe(endpoint)
        last = detail
        if ready:
            print(f"[就绪] 第 {attempt} 次探测成功：{detail}")
            return 0
        if attempt % 5 == 1:
            print(f"[就绪] 等待中（第 {attempt} 次）：{detail}")
        time.sleep(args.interval)

    print(f"[就绪] 超时 {args.timeout}s 仍未就绪，最后一次探测结果：{last}", file=sys.stderr)
    print(
        "\n排查方向：\n"
        "  1) 被测服务是否真的启动了？看启动日志有没有 'Started MesPlatformApplication'\n"
        "  2) 端口对不对？默认 8080；若被沙箱的 SERVER__PORT 覆盖，启动前需 unset SERVER__PORT SERVER__HOST\n"
        "  3) 数据库通不通？访问 /api/ready 看 database 字段是否为 UP\n"
        "  4) profile 对不对？CI/测试应使用 test profile（数据写入 mes_test）\n",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())

"""把 pytest 的 junit.xml 渲染成一份自包含的 HTML 报告。

为什么需要它：pytest 的控制台输出适合开发者，不适合拿给别人看。
Allure 是 M3 的目标（需要额外安装命令行），在那之前先用这个零依赖的版本顶上 ——
双击就能在浏览器打开，截图能直接贴进汇报。

用法：
    python tools/report_html.py
    python tools/report_html.py --junit reports/junit.xml --out reports/测试报告.html
"""

from __future__ import annotations

import argparse
import html
import sys
import xml.etree.ElementTree as ET
from collections import OrderedDict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

MODULE_LABEL = OrderedDict(
    [
        ("test_health", "服务自检"),
        ("test_work_order_lifecycle", "工单主链路"),
        ("test_work_order_rules", "工单业务规则"),
        ("test_quality_rules", "质量检验规则"),
        ("test_material_trace", "物料批次与追溯"),
        ("test_device_data", "设备数采质量"),
        ("test_stats", "统计报表"),
    ]
)


def module_of(classname: str) -> str:
    """从 junit 的 classname 里取出模块名，形如 testcases.test_health.TestHealth → test_health"""
    parts = (classname or "").split(".")
    for part in parts:
        if part.startswith("test_"):
            return part
    return parts[-1] if parts else "(未知)"


def parse(junit_path: Path) -> dict:
    tree = ET.parse(junit_path)
    root = tree.getroot()

    suites = [root] if root.tag == "testsuite" else list(root)
    cases: list[dict] = []

    for suite in suites:
        for case in suite.findall("testcase"):
            failure = case.find("failure")
            error = case.find("error")
            skipped = case.find("skipped")

            if failure is not None:
                status, detail = "failed", failure
            elif error is not None:
                status, detail = "error", error
            elif skipped is not None:
                status, detail = "skipped", skipped
            else:
                status, detail = "passed", None

            cases.append(
                {
                    "name": case.get("name", ""),
                    "classname": case.get("classname", ""),
                    "module": module_of(case.get("classname", "")),
                    "time": float(case.get("time") or 0),
                    "status": status,
                    "message": (detail.get("message") or "").strip() if detail is not None else "",
                    "text": (detail.text or "").strip() if detail is not None and detail.text else "",
                }
            )

    by_module: dict[str, dict] = OrderedDict()
    for m in MODULE_LABEL:
        by_module[m] = {"passed": 0, "failed": 0, "error": 0, "skipped": 0, "cases": [], "time": 0.0}
    for c in cases:
        bucket = by_module.setdefault(
            c["module"], {"passed": 0, "failed": 0, "error": 0, "skipped": 0, "cases": [], "time": 0.0}
        )
        bucket[c["status"]] += 1
        bucket["cases"].append(c)
        bucket["time"] += c["time"]

    total = {
        "passed": sum(b["passed"] for b in by_module.values()),
        "failed": sum(b["failed"] for b in by_module.values()),
        "error": sum(b["error"] for b in by_module.values()),
        "skipped": sum(b["skipped"] for b in by_module.values()),
        "time": sum(b["time"] for b in by_module.values()),
        "count": len(cases),
    }
    return {"total": total, "by_module": by_module}


def pretty_name(name: str) -> str:
    """test_report_on_new[report-on-new] → report_on_new（report-on-new）"""
    label = name
    if "[" in name:
        base, _, param = name.partition("[")
        label = f"{base.rstrip('_')}（{param.rstrip(']')}）"
    return label.split("::")[-1]


def render(data: dict, source: str) -> str:
    t = data["total"]
    pass_rate = (t["passed"] / t["count"] * 100) if t["count"] else 0.0
    all_green = t["failed"] == 0 and t["error"] == 0
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    rows = []
    for module, b in data["by_module"].items():
        if not b["cases"]:
            continue
        label = MODULE_LABEL.get(module, module)
        bad = b["failed"] + b["error"]
        rows.append(
            f"""      <tr>
        <td><span class="mname">{html.escape(label)}</span><span class="mfile">{html.escape(module)}.py</span></td>
        <td class="num">{b['passed'] + bad + b['skipped']}</td>
        <td class="num ok">{b['passed']}</td>
        <td class="num {'bad' if bad else ''}">{bad if bad else '-'}</td>
        <td class="num">{b['time']:.1f}s</td>
        <td><div class="bar"><span style="width:{(b['passed'] / (b['passed'] + bad + b['skipped']) * 100):.0f}%"></span></div></td>
      </tr>"""
        )

    failures = [c for c in (c for b in data["by_module"].values() for c in b["cases"]) if c["status"] in ("failed", "error")]
    if failures:
        blocks = "\n".join(
            f"""    <div class="fail">
      <div class="failhead"><span class="badge">失败</span>{html.escape(pretty_name(c['name']))}
        <span class="where">{html.escape(MODULE_LABEL.get(c['module'], c['module']))}</span></div>
      <pre>{html.escape(c['message'] or c['text'] or '(无附加信息)')}</pre>
    </div>"""
            for c in failures
        )
        fail_section = f"""  <h2>失败明细</h2>
{blocks}"""
    else:
        fail_section = """  <div class="allgood">
    <strong>全部用例通过</strong>
    <span>没有失败项需要排查。</span>
  </div>"""

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>M2 自动化测试报告</title>
<style>
  :root {{
    --bg:#F7F8FA; --surface:#FFF; --border:#DDE2E8; --border2:#C3CBD4;
    --text:#1B2027; --text2:#5B6572; --text3:#8A94A1;
    --green:#1A7F37; --green-bg:#E7F5EC; --red:#CF222E; --red-bg:#FDECEC;
    --mono:ui-monospace,Consolas,"Liberation Mono",monospace;
    --sans:-apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei","PingFang SC",sans-serif;
  }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--text); font-family:var(--sans); font-size:14px; line-height:1.7; }}
  .wrap {{ max-width:1000px; margin:0 auto; padding:36px 28px 90px; }}
  h1 {{ font-size:25px; font-weight:600; margin:0 0 8px; }}
  .sub {{ color:var(--text2); margin:0 0 26px; font-size:13px; }}
  h2 {{ font-size:18px; font-weight:600; margin:38px 0 14px; padding-bottom:9px; border-bottom:1px solid var(--border); }}
  .cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(132px,1fr)); gap:12px; }}
  .card {{ background:var(--surface); border:1px solid var(--border); border-radius:10px; padding:14px 16px; }}
  .card .k {{ font-size:12px; color:var(--text3); margin-bottom:5px; }}
  .card .v {{ font-size:25px; font-weight:600; line-height:1.15; }}
  .card .v.g {{ color:var(--green); }} .card .v.r {{ color:var(--red); }}
  .banner {{ border-radius:10px; padding:15px 18px; margin:18px 0 0; font-size:14px; }}
  .banner.ok {{ background:var(--green-bg); border:1px solid #BEE3C9; color:#136B2C; }}
  .banner.bad {{ background:var(--red-bg); border:1px solid #F3C2C2; color:#8E1B24; }}
  table {{ width:100%; border-collapse:collapse; background:var(--surface); border:1px solid var(--border); border-radius:10px; overflow:hidden; font-size:13px; }}
  th {{ text-align:left; font-size:12px; font-weight:600; color:var(--text2); padding:10px 14px; border-bottom:1px solid var(--border2); }}
  td {{ padding:10px 14px; border-bottom:1px solid var(--border); vertical-align:middle; }}
  tr:last-child td {{ border-bottom:none; }}
  td.num {{ text-align:right; font-family:var(--mono); }}
  td.num.ok {{ color:var(--green); }} td.num.bad {{ color:var(--red); font-weight:600; }}
  .mname {{ display:block; font-weight:500; }}
  .mfile {{ display:block; font-family:var(--mono); font-size:11px; color:var(--text3); }}
  .bar {{ width:96px; height:6px; background:#E8EBEF; border-radius:999px; overflow:hidden; }}
  .bar span {{ display:block; height:100%; background:var(--green); border-radius:999px; }}
  .allgood {{ background:var(--green-bg); border:1px solid #BEE3C9; border-radius:10px; padding:18px 20px; color:#136B2C; }}
  .allgood strong {{ display:block; font-size:15px; margin-bottom:3px; }}
  .allgood span {{ font-size:13px; }}
  .fail {{ background:var(--surface); border:1px solid var(--border); border-left:3px solid var(--red); border-radius:0 10px 10px 0; padding:14px 18px; margin-bottom:12px; }}
  .failhead {{ font-weight:500; margin-bottom:8px; }}
  .badge {{ background:var(--red-bg); color:var(--red); font-size:11px; padding:2px 8px; border-radius:999px; margin-right:8px; }}
  .where {{ float:right; font-size:12px; color:var(--text3); font-weight:400; }}
  pre {{ background:#FAFBFC; border:1px solid var(--border); border-radius:6px; padding:11px 13px; margin:0; overflow-x:auto;
        font-family:var(--mono); font-size:12px; line-height:1.6; color:#3A4552; white-space:pre-wrap; word-break:break-word; }}
  footer {{ margin-top:44px; padding-top:18px; border-top:1px solid var(--border); font-size:12px; color:var(--text3); }}
  @media print {{ body {{ background:#fff; }} .wrap {{ padding:0; }} }}
</style>
</head>
<body>
<div class="wrap">

  <h1>M2 自动化测试报告</h1>
  <p class="sub">被测对象：迷你 MES 系统（mes-platform）&nbsp;·&nbsp; 数据来源：{html.escape(source)}<br>
     用例数据写入 <code>mes_test</code>，与业务库物理隔离；执行结束后自动清场。</p>

  <div class="cards">
    <div class="card"><div class="k">用例总数</div><div class="v">{t['count']}</div></div>
    <div class="card"><div class="k">通过</div><div class="v g">{t['passed']}</div></div>
    <div class="card"><div class="k">失败</div><div class="v {'r' if t['failed'] else ''}">{t['failed']}</div></div>
    <div class="card"><div class="k">错误</div><div class="v {'r' if t['error'] else ''}">{t['error']}</div></div>
    <div class="card"><div class="k">通过率</div><div class="v {'g' if all_green else 'r'}">{pass_rate:.1f}%</div></div>
    <div class="card"><div class="k">总耗时</div><div class="v">{t['time']:.1f}<small style="font-size:13px;font-weight:400;color:var(--text3)">s</small></div></div>
  </div>

  <div class="banner {'ok' if all_green else 'bad'}">
    {'全部通过 —— 被测系统当前状态满足全部已登记的业务规则。' if all_green else f"存在 {t['failed'] + t['error']} 项失败，请查看下方明细。"}
  </div>

  <h2>分模块结果</h2>
  <table>
    <thead>
      <tr><th>模块</th><th style="text-align:right">用例</th><th style="text-align:right">通过</th><th style="text-align:right">失败</th><th style="text-align:right">耗时</th><th>通过占比</th></tr>
    </thead>
    <tbody>
{chr(10).join(rows)}
    </tbody>
  </table>

{fail_section}

  <footer>
    生成时间 {stamp} &nbsp;|&nbsp; 报告由 tools/report_html.py 从 junit.xml 渲染，无外部依赖，可直接离线打开或打印为 PDF。
  </footer>
</div>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="把 junit.xml 渲染成 HTML 测试报告")
    parser.add_argument("--junit", default=str(ROOT / "reports" / "junit.xml"))
    parser.add_argument("--out", default=str(ROOT / "reports" / "测试报告.html"))
    args = parser.parse_args()

    junit_path = Path(args.junit)
    if not junit_path.exists():
        print(f"找不到 junit 报告：{junit_path}")
        print("请先带 --junitxml 跑一次用例：")
        print("  pytest --junitxml=reports/junit.xml")
        return 2

    data = parse(junit_path)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render(data, junit_path.name), encoding="utf-8")

    t = data["total"]
    print(f"报告已生成：{out_path}")
    print(f"合计 {t['count']} 条：通过 {t['passed']} / 失败 {t['failed']} / 错误 {t['error']}")
    return 0 if t["failed"] == 0 and t["error"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

"""通过率趋势页 —— 从执行历史渲染成一张自包含的 HTML。

为什么手写 SVG 而不引图表库：报告要给面试官/同事看，双击就得能开。
引 ECharts 之类就得挂 CDN，断网或内网环境下直接白屏 —— 那是报告最不能被接受的失败方式。

用法：
    python tools/trend.py
    python tools/trend.py --limit 30 --out reports/通过率趋势.html
"""

from __future__ import annotations

import argparse
import html
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from common.history import history_file, load_history, summarize  # noqa: E402

# ---------- 绘图区几何 ----------
W, H = 900, 260
PAD_L, PAD_R, PAD_T, PAD_B = 52, 22, 18, 42
PLOT_W = W - PAD_L - PAD_R
PLOT_H = H - PAD_T - PAD_B


def x_at(index: int, count: int) -> float:
    if count <= 1:
        return PAD_L + PLOT_W / 2
    return PAD_L + PLOT_W * index / (count - 1)


def y_at(rate: float) -> float:
    return PAD_T + PLOT_H * (1 - max(0.0, min(100.0, rate)) / 100)


def render_chart(records: list[dict]) -> str:
    """通过率趋势折线图。失败轮次标红，便于一眼看出哪几轮出了问题。"""
    # 空历史必须先行返回：下面用到了 count-1，没有这个保护会索引越界。
    # 触发场景真实存在 —— 首次使用、或历史文件被清空后直接跑 trend.py。
    if not records:
        return (
            f'<text x="{W / 2:.0f}" y="{H / 2:.0f}" text-anchor="middle" font-size="13" '
            f'fill="#8A94A1">暂无执行记录</text>'
        )

    count = len(records)
    rates = [r.get("pass_rate", 0.0) for r in records]

    parts: list[str] = []

    # 网格与刻度
    for tick in (0, 25, 50, 75, 100):
        y = y_at(tick)
        parts.append(
            f'<line x1="{PAD_L}" y1="{y:.1f}" x2="{W - PAD_R}" y2="{y:.1f}" '
            f'stroke="#E4E8ED" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{PAD_L - 10}" y="{y + 4:.1f}" text-anchor="end" '
            f'font-size="11" fill="#8A94A1" font-family="ui-monospace,monospace">{tick}%</text>'
        )

    if count == 1:
        # 只有一个点时连线没意义，只画点 + 提示
        x, y = x_at(0, 1), y_at(rates[0])
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="#2F6FEB"/>')
        parts.append(
            f'<text x="{x:.1f}" y="{y - 14:.1f}" text-anchor="middle" font-size="12" '
            f'font-weight="500" fill="#1A4FA8">{rates[0]}%</text>'
        )
        parts.append(
            f'<text x="{W / 2:.0f}" y="{H - 12:.0f}" text-anchor="middle" font-size="12" '
            f'fill="#8A94A1">目前仅 1 轮记录，多跑几轮即可看到趋势</text>'
        )
        return "\n".join(parts)

    # 面积（淡色填充，让趋势更易读）
    line_pts = " ".join(f"{x_at(i, count):.1f},{y_at(r):.1f}" for i, r in enumerate(rates))
    area_pts = f"{x_at(0, count):.1f},{PAD_T + PLOT_H:.1f} {line_pts} {x_at(count - 1, count):.1f},{PAD_T + PLOT_H:.1f}"
    parts.append(f'<polygon points="{area_pts}" fill="#EAF1FE"/>')
    parts.append(
        f'<polyline points="{line_pts}" fill="none" stroke="#2F6FEB" stroke-width="2" '
        f'stroke-linejoin="round" stroke-linecap="round"/>'
    )

    # 数据点：有失败/错误的轮次标红
    for i, r in enumerate(records):
        x, y = x_at(i, count), y_at(rates[i])
        bad = r.get("failed", 0) + r.get("error", 0)
        color = "#CF222E" if bad else "#2F6FEB"
        tip = (
            f"{r.get('time', '')} · 通过率 {r.get('pass_rate', 0)}%"
            f" · 通过 {r.get('passed', 0)}/{r.get('total', 0)}"
            f" · 来源 {r.get('label', '-')}"
        )
        parts.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.5" fill="#FFFFFF" stroke="{color}" '
            f'stroke-width="2"><title>{html.escape(tip)}</title></circle>'
        )

    # 首尾与异常轮次的数值标注，不标全部，避免拥挤
    label_idx = {0, count - 1}
    label_idx.update(i for i, r in enumerate(records) if r.get("failed", 0) + r.get("error", 0))
    for i in sorted(label_idx):
        x, y = x_at(i, count), y_at(rates[i])
        bad = records[i].get("failed", 0) + records[i].get("error", 0)
        color = "#CF222E" if bad else "#5B6572"
        parts.append(
            f'<text x="{x:.1f}" y="{y - 12:.1f}" text-anchor="middle" font-size="11" '
            f'fill="{color}">{rates[i]}%</text>'
        )

    # 底部时间轴：最多标 6 个，避免重叠
    step = max(1, count // 6)
    for i in range(0, count, step):
        x = x_at(i, count)
        stamp = records[i].get("time", "")[5:16]
        parts.append(
            f'<text x="{x:.1f}" y="{H - PAD_B + 18:.0f}" text-anchor="middle" '
            f'font-size="10" fill="#8A94A1">{html.escape(stamp)}</text>'
        )

    return "\n".join(parts)


def render_table(records: list[dict]) -> str:
    rows = []
    for r in reversed(records):
        bad = r.get("failed", 0) + r.get("error", 0)
        state = (
            '<span class="pill ok">全绿</span>'
            if bad == 0
            else f'<span class="pill bad">失败 {bad}</span>'
        )
        rows.append(
            f"""      <tr>
        <td class="mono">{html.escape(r.get('time', ''))}</td>
        <td>{html.escape(str(r.get('label', '-')))}</td>
        <td class="num">{r.get('total', 0)}</td>
        <td class="num ok">{r.get('passed', 0)}</td>
        <td class="num {'bad' if bad else ''}">{r.get('failed', 0)}</td>
        <td class="num {'bad' if r.get('error', 0) else ''}">{r.get('error', 0)}</td>
        <td class="num">{r.get('duration', 0):.1f}s</td>
        <td class="num">{r.get('pass_rate', 0)}%</td>
        <td>{state}</td>
      </tr>"""
        )
    return "\n".join(rows)


def render(records: list[dict]) -> str:
    s = summarize(records)
    latest = s["latest"] or {}
    chart = render_chart(records)
    table = render_table(records)

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MES 接口自动化 · 通过率趋势</title>
<style>
  :root {{
    --bg:#F7F8FA; --surface:#FFF; --border:#DDE2E8; --border2:#C3CBD4;
    --text:#1B2027; --text2:#5B6572; --text3:#8A94A1;
    --blue:#2F6FEB; --blue-bg:#EAF1FE; --green:#1A7F37; --green-bg:#E7F5EC;
    --red:#CF222E; --red-bg:#FDECEC;
    --mono:ui-monospace,Consolas,"Liberation Mono",monospace;
    --sans:-apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei","PingFang SC",sans-serif;
  }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--text); font-family:var(--sans); font-size:14px; line-height:1.7; }}
  .wrap {{ max-width:1000px; margin:0 auto; padding:36px 28px 90px; }}
  h1 {{ font-size:25px; font-weight:600; margin:0 0 8px; }}
  .sub {{ color:var(--text2); font-size:13px; margin:0 0 26px; }}
  h2 {{ font-size:18px; font-weight:600; margin:38px 0 14px; padding-bottom:9px; border-bottom:1px solid var(--border); }}
  .cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(140px,1fr)); gap:12px; }}
  .card {{ background:var(--surface); border:1px solid var(--border); border-radius:10px; padding:14px 16px; }}
  .card .k {{ font-size:12px; color:var(--text3); margin-bottom:5px; }}
  .card .v {{ font-size:24px; font-weight:600; line-height:1.15; }}
  .card .v.g {{ color:var(--green); }} .card .v.r {{ color:var(--red); }}
  .card .v small {{ font-size:13px; font-weight:400; color:var(--text3); }}
  .panel {{ background:var(--surface); border:1px solid var(--border); border-radius:10px; padding:16px 18px; }}
  .panel svg {{ display:block; width:100%; height:auto; }}
  table {{ width:100%; border-collapse:collapse; background:var(--surface); border:1px solid var(--border); border-radius:10px; overflow:hidden; font-size:13px; }}
  th {{ text-align:left; font-size:12px; font-weight:600; color:var(--text2); padding:10px 12px; border-bottom:1px solid var(--border2); white-space:nowrap; }}
  td {{ padding:9px 12px; border-bottom:1px solid var(--border); }}
  tr:last-child td {{ border-bottom:none; }}
  td.num {{ text-align:right; font-family:var(--mono); }}
  td.num.ok {{ color:var(--green); }} td.num.bad {{ color:var(--red); font-weight:600; }}
  td.mono {{ font-family:var(--mono); font-size:12px; color:var(--text2); white-space:nowrap; }}
  .pill {{ font-size:11px; padding:2px 8px; border-radius:999px; white-space:nowrap; }}
  .pill.ok {{ background:var(--green-bg); color:var(--green); }}
  .pill.bad {{ background:var(--red-bg); color:var(--red); }}
  .empty {{ background:var(--surface); border:1px dashed var(--border2); border-radius:10px; padding:40px; text-align:center; color:var(--text3); }}
  footer {{ margin-top:44px; padding-top:18px; border-top:1px solid var(--border); font-size:12px; color:var(--text3); }}
  code {{ font-family:var(--mono); font-size:12px; background:#EEF1F5; padding:1px 5px; border-radius:4px; }}
  @media print {{ body {{ background:#fff; }} .wrap {{ padding:0; }} }}
</style>
</head>
<body>
<div class="wrap">

  <h1>MES 接口自动化 · 通过率趋势</h1>
  <p class="sub">
    数据来源：<code>history/api-test-history.jsonl</code>（每跑一轮追加一条，随仓库累积）。<br>
    被测对象：迷你 MES 系统（mes-platform）&nbsp;·&nbsp; 用例库：mes-autotest
  </p>

  <div class="cards">
    <div class="card"><div class="k">累计执行轮次</div><div class="v">{s['runs']}</div></div>
    <div class="card"><div class="k">平均通过率</div><div class="v">{s['avg_pass_rate']}<small>%</small></div></div>
    <div class="card"><div class="k">最新通过率</div><div class="v {'g' if latest.get('failed', 0) + latest.get('error', 0) == 0 else 'r'}">{latest.get('pass_rate', 0)}<small>%</small></div></div>
    <div class="card"><div class="k">连续全绿</div><div class="v g">{s['streak']}<small> 轮</small></div></div>
    <div class="card"><div class="k">最新用例数</div><div class="v">{s['total_cases_latest']}</div></div>
  </div>

  <h2>通过率变化</h2>
  {'' if records else '<div class="empty">还没有执行记录。跑一次 <code>pytest</code> 即会写入首条记录。</div>'}
  {f'<div class="panel"><svg viewBox="0 0 {W} {H}" role="img" aria-label="通过率趋势折线图">{chart}</svg></div>' if records else ''}
  <p class="sub" style="margin-top:10px">
    蓝色点为全绿轮次，红色点为存在失败的轮次（鼠标悬停可见该轮详情）。
    首次与末次、以及所有异常轮次都标出数值，中间轮次只在图上成点以免拥挤。
  </p>

  {f'''<h2>全部执行记录</h2>
  <table>
    <thead>
      <tr><th>时间</th><th>来源</th><th style="text-align:right">用例</th><th style="text-align:right">通过</th>
          <th style="text-align:right">失败</th><th style="text-align:right">错误</th>
          <th style="text-align:right">耗时</th><th style="text-align:right">通过率</th><th>结果</th></tr>
    </thead>
    <tbody>
{table}
    </tbody>
  </table>''' if records else ''}

  <footer>
    由 tools/trend.py 生成 &nbsp;|&nbsp; 无外部依赖，可离线打开或打印为 PDF
  </footer>
</div>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="渲染通过率趋势页")
    parser.add_argument("--limit", type=int, default=0, help="只取最近 N 轮（0 = 全部）")
    parser.add_argument("--out", default=str(ROOT / "reports" / "通过率趋势.html"))
    args = parser.parse_args()

    records = load_history(args.limit)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render(records), encoding="utf-8")

    print(f"趋势页已生成：{out_path}")
    if records:
        s = summarize(records)
        print(
            f"  累计 {s['runs']} 轮 · 平均通过率 {s['avg_pass_rate']}%"
            f" · 连续全绿 {s['streak']} 轮"
        )
    else:
        print(f"  （历史文件为空或不存在：{history_file()}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())

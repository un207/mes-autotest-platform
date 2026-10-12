"""回归：统计报表。

统计最容易出问题的地方是口径 —— 数字算错比接口报错更危险，因为它不报错。
所以这里不只断言「接口通」，还拿库里真实数据反算一遍，验证聚合口径一致。
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from common import report
from common.assert_helper import assert_ok, assert_rejected, assert_true

pytestmark = [pytest.mark.smoke, pytest.mark.db]

OVERVIEW_KEYS = [
    "totalOrders",
    "openOrders",
    "closedOrders",
    "totalPlanQty",
    "totalFinishedQty",
    "totalQualifiedQty",
    "totalDefectiveQty",
    "yieldRate",
    "inspectionCount",
    "inspectionFailCount",
    "batchCount",
    "deviceDataCount",
    "deviceAbnormalCount",
]


class TestOverview:

    @report.title("平台总览：字段齐全且与库中实际计数一致")
    def test_overview_consistency(self, api, ep, db, factory):
        with report.step("造一张已关闭工单，确保总览有可对照的数据"):
            order = factory.create_dispatched_order(plan_qty=100)
            factory.report(order["orderNo"], report_qty=30, qualified=28, defective=2)
            res = api.put(ep.path("work_order_close", orderNo=order["orderNo"]), json_body={"remark": "总览对照"})
            assert res.ok, f"关闭工单失败\n  {res.describe()}"

        with report.step("拉取总览，断言字段齐全"):
            res = api.get(ep.path("stats_overview"))
            data = assert_ok(res, "平台总览")
            report.attach_json("总览响应", data)

            missing = [k for k in OVERVIEW_KEYS if k not in data]
            assert_true(not missing, f"总览缺少字段 {missing}")

        with report.step("反算核对：工单总数、已关闭数应与库中一致"):
            db_total = db.query_scalar("SELECT COUNT(*) AS c FROM mes_work_order WHERE deleted = 0")
            db_closed = db.query_scalar(
                "SELECT COUNT(*) AS c FROM mes_work_order WHERE deleted = 0 AND status = 'CLOSED'"
            )
            assert_true(
                data["totalOrders"] == db_total,
                f"总览工单总数 {data['totalOrders']} 与库中 {db_total} 不一致",
            )
            assert_true(
                data["closedOrders"] == db_closed,
                f"总览已关闭数 {data['closedOrders']} 与库中 {db_closed} 不一致",
            )

        with report.step("反算核对：累计合格/不良/报工量应与库中一致"):
            row = db.query_one(
                "SELECT IFNULL(SUM(finished_qty),0) AS f, IFNULL(SUM(qualified_qty),0) AS q, "
                "IFNULL(SUM(defective_qty),0) AS d FROM mes_work_order WHERE deleted = 0"
            )
            assert_true(data["totalFinishedQty"] == row["f"], f"累计报工 {data['totalFinishedQty']} vs 库中 {row['f']}")
            assert_true(data["totalQualifiedQty"] == row["q"], f"累计合格 {data['totalQualifiedQty']} vs 库中 {row['q']}")
            assert_true(data["totalDefectiveQty"] == row["d"], f"累计不良 {data['totalDefectiveQty']} vs 库中 {row['d']}")

        with report.step("良率口径应为 合格 / 报工 × 100"):
            if row["f"]:
                # MySQL 的 SUM() 返回 DECIMAL，pymysql 映射为 Decimal，参与减法前先转 float
                expected = round(float(row["q"]) / float(row["f"]) * 100, 2)
                assert_true(
                    abs(float(data["yieldRate"]) - expected) <= 0.01,
                    f"良率应为 {expected}%，实际 {data['yieldRate']}%",
                )

        with report.step("数采与异常计数也应与库中一致"):
            db_device = db.query_scalar("SELECT COUNT(*) AS c FROM mes_device_data WHERE deleted = 0")
            db_abnormal = db.query_scalar(
                "SELECT COUNT(*) AS c FROM mes_device_data WHERE deleted = 0 AND quality_flag <> 'OK'"
            )
            assert_true(data["deviceDataCount"] == db_device, f"数采条数 {data['deviceDataCount']} vs 库中 {db_device}")
            assert_true(
                data["deviceAbnormalCount"] == db_abnormal,
                f"异常数采条数 {data['deviceAbnormalCount']} vs 库中 {db_abnormal}",
            )


class TestProduction:

    @report.title("产量日报：按日期区间返回，且结构与口径正确")
    def test_production_default_range(self, api, ep, db, factory):
        with report.step("造一张今天的在产工单，确保日报有数据"):
            order = factory.create_dispatched_order(plan_qty=80)
            factory.report(order["orderNo"], report_qty=40, qualified=38, defective=2)

        with report.step("不传参数取默认区间（近 7 天）"):
            res = api.get(ep.path("stats_production"))
            rows = assert_ok(res, "产量日报")
            report.attach_json("日报结果", rows)

            assert_true(isinstance(rows, list), "日报应返回列表")
            assert_true(len(rows) >= 1, "本轮已造出当天工单，日报不应为空")

            first = rows[0]
            for key in ("statDate", "lineCode", "orderCount", "planQty", "finishedQty",
                        "qualifiedQty", "defectiveQty", "yieldRate"):
                assert_true(key in first, f"日报行缺少字段 {key}，实际字段 {sorted(first.keys())}")

        with report.step("行内良率口径应为 合格 / 报工 × 100"):
            for row in rows:
                if row["finishedQty"]:
                    expected = round(row["qualifiedQty"] / row["finishedQty"] * 100, 2)
                    assert_true(
                        abs(float(row["yieldRate"]) - expected) <= 0.01,
                        f"{row['statDate']} {row['lineCode']} 行良率应为 {expected}%，实际 {row['yieldRate']}%",
                    )

    @report.title("产量日报：显式区间与产线筛选")
    def test_production_explicit_range_and_line(self, api, ep, factory):
        today = date.today()

        with report.step("造一张产线为 L-M2-STAT 的工单"):
            order = factory.create_order(plan_qty=50)
            factory.dispatch_order(order["orderNo"], line_code="L-M2-STAT")
            factory.report(order["orderNo"], report_qty=20, qualified=19, defective=1)

        with report.step("按今天为区间 + 指定产线查询，应命中该产线"):
            res = api.get(
                ep.path("stats_production"),
                params={"from": today.isoformat(), "to": today.isoformat(), "lineCode": "L-M2-STAT"},
            )
            rows = assert_ok(res, "按产线查日报")
            report.attach_json("日报结果", rows)

            assert_true(len(rows) >= 1, "应命中该产线的当日统计行")
            assert_true(
                all(r["lineCode"] == "L-M2-STAT" for r in rows),
                f"结果中不应出现其他产线，实际 {[r['lineCode'] for r in rows]}",
            )

    @report.title("产量日报：区间参数非法应被拒绝")
    def test_production_invalid_range(self, api, ep):
        today = date.today()

        with report.step("结束日期早于开始日期，应拒绝"):
            res = api.get(
                ep.path("stats_production"),
                params={"from": today.isoformat(), "to": (today - timedelta(days=5)).isoformat()},
            )
            report.attach_json("响应", res.raw_text)
            assert_rejected(res, 40000, "结束早于开始")

        with report.step("区间跨度超过 92 天上限，应拒绝"):
            res = api.get(
                ep.path("stats_production"),
                params={"from": (today - timedelta(days=200)).isoformat(), "to": today.isoformat()},
            )
            report.attach_json("响应", res.raw_text)
            assert_rejected(res, 40000, "区间过宽")

        with report.step("日期格式非法，应拒绝"):
            res = api.get(ep.path("stats_production"), params={"from": "not-a-date"})
            report.attach_json("响应", res.raw_text)
            assert_rejected(res, 40000, "日期格式非法")


class TestYieldRanking:

    @report.title("低良率排行：按良率升序返回，且只含有报工的工单")
    def test_low_yield_orders(self, api, ep, factory):
        with report.step("造一张低良率工单（良率 60%）"):
            order = factory.create_dispatched_order(plan_qty=100)
            factory.report(order["orderNo"], report_qty=50, qualified=30, defective=20)

        with report.step("查询排行"):
            res = api.get(ep.path("stats_yield_orders"), params={"limit": 10})
            rows = assert_ok(res, "低良率排行")
            report.attach_json("排行结果", rows)

            assert_true(isinstance(rows, list), "排行应返回列表")
            assert_true(len(rows) >= 1, "本轮已造出低良率工单，排行不应为空")

            order_nos = [r["orderNo"] for r in rows]
            assert_true(order["orderNo"] in order_nos, "本轮造的低良率工单应出现在排行中")

            for r in rows:
                assert_true(r["finishedQty"] > 0, "排行只应包含有报工的工单")

            rates = [float(r["yieldRate"]) for r in rows]
            assert_true(rates == sorted(rates), f"排行应按良率升序，实际 {rates}")

    @report.title("低良率排行：limit 越界应被拒绝")
    def test_yield_limit_validation(self, api, ep):
        with report.step("limit=0，低于下界"):
            res = api.get(ep.path("stats_yield_orders"), params={"limit": 0})
            assert_rejected(res, 40000, "limit 下界")

        with report.step("limit=101，高于上界 100"):
            res = api.get(ep.path("stats_yield_orders"), params={"limit": 101})
            assert_rejected(res, 40000, "limit 上界")

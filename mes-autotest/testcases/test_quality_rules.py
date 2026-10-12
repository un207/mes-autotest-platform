"""回归：质量检验规则。

核心约束两条：结论由数量推导（不允许人工背离）、有不良必须有不良代码（否则追溯断链）。
"""

from __future__ import annotations

import pytest

from common import report
from common.assert_helper import assert_fields, assert_ok, assert_rejected, assert_true
from common.config_loader import load_cases

CASES = load_cases("quality_rules")

pytestmark = [pytest.mark.regression, pytest.mark.db]


def build_inspected_order(factory, with_batch: bool = False):
    """准备一张可质检的工单（已派工 + 已报工），可选配一个绑定批次。"""
    order = factory.create_in_progress_order(plan_qty=200, first_report=50)
    order_no = order["orderNo"]
    batch_no = None
    if with_batch:
        batch = factory.create_batch(order_no=order_no, qty=100)
        batch_no = batch["batchNo"]
    return order_no, batch_no


def build_quality_body(case, order_no, batch_no, factory) -> dict:
    body: dict = {
        "orderNo": order_no,
        "inspectType": case.get("inspect_type", "IPQC"),
        "inspectQty": case["inspect_qty"],
        "inspector": f"{factory.run_id}-QC",
    }
    if batch_no:
        body["batchNo"] = batch_no
    for src, dst in (("qualified", "qualifiedQty"), ("defective", "defectiveQty"),
                     ("defect_code", "defectCode"), ("result", "result")):
        if case.get(src) is not None:
            body[dst] = case[src]
    # 用例显式声明要缺哪个字段时，把它删掉——否则默认值会顶上来，用例就测不到「必填缺失」
    for field_name in case.get("omit", []):
        body.pop(field_name, None)
    return body


class TestResultDerivation:

    @pytest.mark.parametrize("case", CASES["result_derive"], ids=lambda c: c["id"])
    @report.title("质检结论：由数量自动推导")
    def test_result_is_derived_from_quantity(self, api, ep, db, factory, case):
        order_no, batch_no = build_inspected_order(factory, with_batch=True)
        body = build_quality_body(case, order_no, batch_no, factory)

        with report.step(f"场景：{case['desc']}"):
            res = api.post(ep.path("quality_inspections"), json_body=body)
            data = assert_ok(res, case["desc"])
            report.attach_json("请求体", body)
            report.attach_json("质检响应", data)

        with report.step(f"断言结论为 {case['expect_result']}"):
            assert_fields(data, result=case["expect_result"])

        with report.step("断言数量推算结果"):
            if case.get("expect_qualified") is not None:
                assert_fields(data, qualifiedQty=case["expect_qualified"])
            if case.get("expect_defective") is not None:
                assert_fields(data, defectiveQty=case["expect_defective"])

        with report.step("断言不良代码按输入落库 / 置空"):
            # 用例未显式声明期望值时，默认「输入的代码应被原样保存」
            expected_code = case.get("expect_defect_code", case.get("defect_code"))
            assert_true(
                data.get("defectCode") == expected_code,
                f"不良代码应为 {expected_code!r}，实际 {data.get('defectCode')!r}",
            )

        with report.step("[落库] 质检记录与追溯节点落表"):
            row = db.get_row("mes_quality_inspection", {"inspect_no": data["inspectNo"]})
            assert_true(row is not None, "库里查不到刚录入的质检记录")
            assert_true(row["result"] == case["expect_result"], f"库中结论应为 {case['expect_result']}，实际 {row['result']}")
            assert_true(
                row["qualified_qty"] + row["defective_qty"] == row["inspect_qty"],
                "落库后数量仍应守恒",
            )

            if batch_no:
                nodes = db.query_all(
                    "SELECT * FROM mes_trace_record WHERE batch_no = %s AND node_type = 'INSPECT'",
                    [batch_no],
                )
                assert_true(len(nodes) == 1, f"带批次的质检应落下 1 条 INSPECT 节点，实际 {len(nodes)} 条")


class TestQualityReject:

    @pytest.mark.parametrize("case", CASES["reject_cases"], ids=lambda c: c["id"])
    @report.title("质检拒绝场景：人为矛盾与必填缺失")
    def test_illegal_inspection_rejected(self, api, ep, factory, case):
        order_no, batch_no = build_inspected_order(factory, with_batch=False)
        body = build_quality_body(case, order_no, batch_no, factory)

        with report.step(f"场景：{case['desc']}"):
            res = api.post(ep.path("quality_inspections"), json_body=body)
            report.attach_json("请求体", body)
            report.attach_json("响应", res.raw_text)

        with report.step(f"断言被拒绝，业务码 {case['expect_code']}"):
            assert_rejected(res, case["expect_code"], case["desc"])


class TestQualityAssociation:

    @report.title("质检关联校验：工单与批次必须存在且一致")
    def test_inspection_requires_existing_order(self, api, ep, factory):
        ghost = f"WO-NOT-EXIST-{factory.run_id}"

        with report.step("对不存在的工单录入质检"):
            res = api.post(
                ep.path("quality_inspections"),
                json_body={
                    "orderNo": ghost,
                    "inspectType": "IQC",
                    "inspectQty": 10,
                    "qualifiedQty": 10,
                    "inspector": f"{factory.run_id}-QC",
                },
            )
            report.attach_json("响应", res.raw_text)
            assert_rejected(res, 40400, "不存在工单")

    @report.title("质检关联校验：不存在的批次应被拒绝")
    def test_inspection_requires_existing_batch(self, api, ep, factory):
        order_no, _ = build_inspected_order(factory)

        with report.step("引用一个不存在的批次号"):
            res = api.post(
                ep.path("quality_inspections"),
                json_body={
                    "orderNo": order_no,
                    "batchNo": f"B-NOT-EXIST-{factory.run_id}",
                    "inspectType": "IQC",
                    "inspectQty": 10,
                    "qualifiedQty": 10,
                    "inspector": f"{factory.run_id}-QC",
                },
            )
            report.attach_json("响应", res.raw_text)
            assert_rejected(res, 40400, "不存在批次")

    @report.title("质检关联校验：批次已绑其他工单时不得交叉质检")
    def test_inspection_rejects_batch_bound_to_other_order(self, api, ep, factory):
        order_a, batch_no = build_inspected_order(factory, with_batch=True)
        order_b = factory.create_in_progress_order(plan_qty=100, first_report=10)

        with report.step(f"用挂在工单 A 的批次去给工单 B 做质检"):
            res = api.post(
                ep.path("quality_inspections"),
                json_body={
                    "orderNo": order_b["orderNo"],
                    "batchNo": batch_no,
                    "inspectType": "IQC",
                    "inspectQty": 10,
                    "qualifiedQty": 10,
                    "inspector": f"{factory.run_id}-QC",
                },
            )
            report.attach_json("响应", res.raw_text)

        with report.step("断言被拒绝（防止把 A 的料记到 B 的质检上）"):
            assert_rejected(res, 40900, "批次与工单不一致")


class TestQualityQuery:

    @report.title("不良追溯：按工单查不良明细")
    def test_defects_by_order(self, api, ep, factory):
        order_no, batch_no = build_inspected_order(factory, with_batch=True)

        with report.step("先录入一条合格、一条不合格"):
            for defective, code in ((0, None), (3, "D-M2-不良A")):
                body = {
                    "orderNo": order_no,
                    "batchNo": batch_no,
                    "inspectType": "IPQC",
                    "inspectQty": 10,
                    "qualifiedQty": 10 - defective,
                    "inspector": f"{factory.run_id}-QC",
                }
                if defective:
                    body["defectiveQty"] = defective
                    body["defectCode"] = code
                assert_ok(api.post(ep.path("quality_inspections"), json_body=body), "录入质检")

        with report.step("查询该工单的不良明细，应只返回不合格的那条"):
            res = api.get(ep.path("quality_defects_by_order", orderNo=order_no))
            defects = assert_ok(res, "不良追溯")
            report.attach_json("不良明细", defects)

            assert_true(len(defects) == 1, f"应只返回 1 条不良，实际 {len(defects)}")
            assert_true(defects[0]["result"] == "FAIL", "返回的记录结论应为 FAIL")
            assert_true(defects[0]["defectCode"] == "D-M2-不良A", "应带出不良代码")

    @report.title("不良追溯：不存在的工单应返回 40400")
    def test_defects_by_ghost_order(self, api, ep, factory):
        res = api.get(ep.path("quality_defects_by_order", orderNo=f"WO-NOT-EXIST-{factory.run_id}"))
        report.attach_json("响应", res.raw_text)
        assert_rejected(res, 40400, "不存在工单")

    @report.title("不良代码分布统计：返回结构正确")
    def test_defect_summary(self, api, ep, factory):
        with report.step("构造一条带不良代码的质检"):
            order_no, batch_no = build_inspected_order(factory, with_batch=True)
            assert_ok(
                api.post(
                    ep.path("quality_inspections"),
                    json_body={
                        "orderNo": order_no,
                        "batchNo": batch_no,
                        "inspectType": "IPQC",
                        "inspectQty": 20,
                        "qualifiedQty": 16,
                        "defectiveQty": 4,
                        "defectCode": "D-M2-分布统计",
                        "inspector": f"{factory.run_id}-QC",
                    },
                ),
                "录入质检",
            )

        with report.step("查询不良分布，结构应为 代码/次数/数量"):
            res = api.get(ep.path("quality_defect_summary"))
            rows = assert_ok(res, "不良分布")
            report.attach_json("不良分布", rows)

            assert_true(isinstance(rows, list), "不良分布应返回列表")
            assert_true(len(rows) >= 1, "本轮已造出不良数据，分布结果不应为空")
            first = rows[0]
            for key in ("defectCode", "cnt", "defectiveQty"):
                assert_true(key in first, f"分布结果缺少字段 {key}，实际字段 {sorted(first.keys())}")

    @report.title("质检单详情：按质检单号可查")
    def test_inspection_detail(self, api, ep, factory):
        order_no, batch_no = build_inspected_order(factory, with_batch=True)

        with report.step("先录入一条质检"):
            created = assert_ok(
                api.post(
                    ep.path("quality_inspections"),
                    json_body={
                        "orderNo": order_no,
                        "batchNo": batch_no,
                        "inspectType": "FQC",
                        "inspectQty": 10,
                        "qualifiedQty": 10,
                        "inspector": f"{factory.run_id}-QC",
                    },
                ),
                "录入质检",
            )

        with report.step("按质检单号查详情"):
            res = api.get(ep.path("quality_detail", inspectNo=created["inspectNo"]))
            detail = assert_ok(res, "质检详情")
            assert_fields(detail, inspectNo=created["inspectNo"], orderNo=order_no)

        with report.step("查询不存在的质检单号，应返回 40400"):
            res = api.get(ep.path("quality_detail", inspectNo=f"QI-NOT-EXIST-{factory.run_id}"))
            assert_rejected(res, 40400, "不存在质检单")

    @report.title("质检分页：可按结论与类型筛选")
    def test_inspection_page_filters(self, api, ep, factory):
        order_no, batch_no = build_inspected_order(factory, with_batch=True)

        with report.step("录入一条不合格记录"):
            assert_ok(
                api.post(
                    ep.path("quality_inspections"),
                    json_body={
                        "orderNo": order_no,
                        "batchNo": batch_no,
                        "inspectType": "IPQC",
                        "inspectQty": 10,
                        "qualifiedQty": 7,
                        "defectiveQty": 3,
                        "defectCode": "D-M2-筛选",
                        "inspector": f"{factory.run_id}-QC",
                    },
                ),
                "录入质检",
            )

        with report.step("按 result=FAIL 筛选，应能命中该工单的记录"):
            res = api.get(ep.path("quality_inspections"), params={"result": "FAIL", "orderNo": order_no, "pageSize": 50})
            page = assert_ok(res, "质检分页")
            report.attach_json("分页结果", page)

            assert_true(page["total"] == 1, f"应命中 1 条 FAIL 记录，实际 {page['total']}")
            assert_true(page["records"][0]["orderNo"] == order_no, "命中记录的工单号应正确")

"""回归：物料批次与追溯。

追溯的规矩是「不串线」：一个批次只能绑一个工单，已消耗的不能再动。
追溯链要能双向走通 —— 从批次查流向，从工单查用料。
"""

from __future__ import annotations

import pytest

from common import report
from common.assert_helper import assert_fields, assert_ok, assert_rejected, assert_true

pytestmark = [pytest.mark.regression, pytest.mark.db]


def build_order(factory, plan_qty: int = 100):
    return factory.create_in_progress_order(plan_qty=plan_qty, first_report=10)


class TestBatchLifecycle:

    @report.title("批次建档：绑定工单进 IN_USE，未绑定进 IN_STOCK")
    def test_create_batch_status(self, api, ep, db, factory):
        order = build_order(factory)

        with report.step("建档时绑定工单，状态应为 IN_USE"):
            bound = factory.create_batch(order_no=order["orderNo"], qty=100)
            assert_fields(bound, orderNo=order["orderNo"], status="IN_USE")

            row = db.get_row("mes_material_batch", {"batch_no": bound["batchNo"]})
            assert_true(row is not None, "库里查不到刚创建的批次")
            assert_true(row["status"] == "IN_USE", f"库中状态应为 IN_USE，实际 {row['status']}")

        with report.step("建档时不绑工单，状态应为 IN_STOCK"):
            free = factory.create_batch(qty=50)
            assert_fields(free, status="IN_STOCK")
            assert_true(free.get("orderNo") in (None, ""), f"未绑定时 orderNo 应为空，实际 {free.get('orderNo')!r}")

    @report.title("批次绑定：未绑定批次可绑工单，改绑他单应被拒绝")
    def test_bind_batch(self, api, ep, db, factory):
        order_a = build_order(factory)
        order_b = build_order(factory)
        free = factory.create_batch(qty=80)

        with report.step("把在库批次绑定到工单 A"):
            res = api.put(
                ep.path("material_bind", batchNo=free["batchNo"]),
                params={"orderNo": order_a["orderNo"]},
            )
            data = assert_ok(res, "批次绑定")
            report.attach_json("绑定响应", data)
            assert_fields(data, orderNo=order_a["orderNo"], status="IN_USE")

        with report.step("[落库] 绑定关系已持久化"):
            row = db.get_row("mes_material_batch", {"batch_no": free["batchNo"]})
            assert_true(row["order_no"] == order_a["orderNo"], "库中绑定工单应为 A")

        with report.step("改绑到工单 B，应被拒绝（防止追溯串线）"):
            res = api.put(
                ep.path("material_bind", batchNo=free["batchNo"]),
                params={"orderNo": order_b["orderNo"]},
            )
            report.attach_json("响应", res.raw_text)
            assert_rejected(res, 40900, "改绑工单")

        with report.step("绑定不存在工单，应返回 40400"):
            # 必须用一个「尚未绑定」的批次，否则会先命中「不允许改绑」而测不到目标分支
            fresh = factory.create_batch(qty=20)
            res = api.put(
                ep.path("material_bind", batchNo=fresh["batchNo"]),
                params={"orderNo": f"WO-NOT-EXIST-{factory.run_id}"},
            )
            report.attach_json("响应", res.raw_text)
            assert_rejected(res, 40400, "绑定不存在工单")

        with report.step("绑定不存在的批次，应返回 40400"):
            res = api.put(
                ep.path("material_bind", batchNo=f"B-NOT-EXIST-{factory.run_id}"),
                params={"orderNo": order_a["orderNo"]},
            )
            assert_rejected(res, 40400, "不存在批次")

    @report.title("批次出货：置为已消耗并落 OUTBOUND 节点，重复出货应被拒绝")
    def test_outbound(self, api, ep, db, factory):
        order = build_order(factory)
        batch = factory.create_batch(order_no=order["orderNo"], qty=60)
        batch_no = batch["batchNo"]

        with report.step("出货消耗"):
            res = api.put(
                ep.path("material_outbound", batchNo=batch_no),
                params={"operator": f"{factory.run_id}-WH"},
            )
            data = assert_ok(res, "批次出货")
            report.attach_json("出货响应", data)
            assert_fields(data, status="CONSUMED")

        with report.step("[落库] 状态已置为已消耗，且落下 OUTBOUND 追溯节点"):
            row = db.get_row("mes_material_batch", {"batch_no": batch_no})
            assert_true(row["status"] == "CONSUMED", f"库中状态应为 CONSUMED，实际 {row['status']}")

            outbound = db.query_all(
                "SELECT * FROM mes_trace_record WHERE batch_no = %s AND node_type = 'OUTBOUND'", [batch_no]
            )
            assert_true(len(outbound) == 1, f"应有 1 条 OUTBOUND 节点，实际 {len(outbound)} 条")

        with report.step("重复出货，应被拒绝"):
            res = api.put(ep.path("material_outbound", batchNo=batch_no))
            report.attach_json("响应", res.raw_text)
            assert_rejected(res, 40900, "重复出货")

        with report.step("已消耗的批次不可再绑定工单"):
            res = api.put(
                ep.path("material_bind", batchNo=batch_no),
                params={"orderNo": order["orderNo"]},
            )
            assert_rejected(res, 40900, "已消耗批次绑定")

    @report.title("冻结批次：不允许出货")
    def test_frozen_batch_cannot_outbound(self, api, ep, db, factory):
        order = build_order(factory)
        batch = factory.create_batch(order_no=order["orderNo"], qty=40)
        batch_no = batch["batchNo"]

        with report.step("用测试通道把批次置为冻结（当前无冻结接口，直接改状态造景）"):
            affected = db.execute(
                "UPDATE mes_material_batch SET status = %s WHERE batch_no = %s",
                ["FROZEN", batch_no],
            )
            assert_true(affected == 1, f"造景失败：应更新 1 行，实际 {affected} 行")

        with report.step("尝试出货，应被拒绝"):
            res = api.put(ep.path("material_outbound", batchNo=batch_no))
            report.attach_json("响应", res.raw_text)
            assert_rejected(res, 40900, "冻结批次出货")

    @report.title("批次建档：重复批次号应被拒绝")
    def test_duplicate_batch_no(self, api, ep, factory):
        first = factory.create_batch(qty=10)

        with report.step(f"用已存在的批次号 {first['batchNo']} 再次建档"):
            res = api.post(
                ep.path("material_batches"),
                json_body={
                    "batchNo": first["batchNo"],
                    "materialCode": factory.unique("M"),
                    "materialName": "重复批次号测试",
                    "qty": 10,
                    "unit": "件",
                },
            )
            report.attach_json("响应", res.raw_text)
            assert_rejected(res, 40901, "重复批次号")

    @report.title("批次建档：引用不存在的工单应被拒绝")
    def test_create_batch_with_ghost_order(self, api, ep, factory):
        res = api.post(
            ep.path("material_batches"),
            json_body={
                "materialCode": factory.unique("M"),
                "materialName": "幽灵工单批次",
                "orderNo": f"WO-NOT-EXIST-{factory.run_id}",
                "qty": 10,
                "unit": "件",
            },
        )
        report.attach_json("响应", res.raw_text)
        assert_rejected(res, 40400, "引用不存在工单")

    @report.title("批次建档：数量为 0 应被拒绝")
    def test_create_batch_zero_qty(self, api, ep, factory):
        res = api.post(
            ep.path("material_batches"),
            json_body={
                "materialCode": factory.unique("M"),
                "materialName": "零数量批次",
                "qty": 0,
            },
        )
        report.attach_json("响应", res.raw_text)
        assert_rejected(res, 40000, "批次数量为 0")


class TestTraceQuery:

    @report.title("双向追溯：正反两向都能走通且节点完整")
    def test_trace_both_directions(self, api, ep, factory):
        order = build_order(factory)
        order_no = order["orderNo"]
        batch = factory.create_batch(order_no=order_no, qty=100)
        batch_no = batch["batchNo"]

        with report.step("追加一笔报工与一次质检，凑足四类节点中的三类"):
            factory.report(order_no, report_qty=20, qualified=19, defective=1)
            assert_ok(
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

        with report.step("正向追溯：批次 → 流向工单 + 全链路节点"):
            res = api.get(ep.path("trace_by_batch", batchNo=batch_no))
            data = assert_ok(res, "正向追溯")
            report.attach_json("正向追溯", data)

            assert_true(data["boundOrderNo"] == order_no, "应反查到所绑工单")
            assert_true(data["batch"]["batchNo"] == batch_no, "应带出批次基本信息")
            node_types = [n["nodeType"] for n in data["nodes"]]
            assert_true(
                node_types == ["INBOUND", "PRODUCE", "INSPECT"],
                f"节点应体现业务先后顺序，实际 {node_types}",
            )

        with report.step("反向追溯：工单 → 用料批次 + 节点流水 + 不良明细"):
            res = api.get(ep.path("trace_by_order", orderNo=order_no))
            data = assert_ok(res, "反向追溯")
            report.attach_json("反向追溯", data)

            assert_true(len(data["batches"]) == 1, f"应关联 1 个批次，实际 {len(data['batches'])}")
            assert_true(len(data["nodes"]) >= 3, "节点流水应包含入库、投产、检验")
            assert_true(data["defects"] == [], "本例质检全部合格，不良明细应为空列表")

    @report.title("追溯查询：不存在的批次 / 工单应返回 40400")
    def test_trace_ghost(self, api, ep, factory):
        with report.step("追溯不存在的批次"):
            res = api.get(ep.path("trace_by_batch", batchNo=f"B-NOT-EXIST-{factory.run_id}"))
            assert_rejected(res, 40400, "不存在批次")

        with report.step("追溯不存在的工单"):
            res = api.get(ep.path("trace_by_order", orderNo=f"WO-NOT-EXIST-{factory.run_id}"))
            assert_rejected(res, 40400, "不存在工单")


class TestBatchQuery:

    @report.title("批次查询：分页、按工单、按状态筛选")
    def test_batch_queries(self, api, ep, factory):
        order = build_order(factory)
        order_no = order["orderNo"]
        bound = factory.create_batch(order_no=order_no, qty=30)
        free = factory.create_batch(qty=20)

        with report.step("按工单查批次，应命中已绑定的那个"):
            res = api.get(ep.path("material_by_order", orderNo=order_no))
            rows = assert_ok(res, "按工单查批次")
            report.attach_json("按工单查批次", rows)
            nos = [r["batchNo"] for r in rows]
            assert_true(bound["batchNo"] in nos, "应能查到绑定到该工单的批次")
            assert_true(free["batchNo"] not in nos, "不应查到未绑定到该工单的批次")

        with report.step("按状态 IN_STOCK 筛选，应命中在库批次"):
            res = api.get(ep.path("material_batches"), params={"status": "IN_STOCK", "keyword": factory.run_id})
            page = assert_ok(res, "按状态筛选")
            report.attach_json("分页结果", page)
            assert_true(page["total"] >= 1, f"应至少命中 1 条在库批次，实际 {page['total']}")
            assert_true(
                all(r["status"] == "IN_STOCK" for r in page["records"]),
                "筛选结果中不应出现非在库状态的批次",
            )

        with report.step("批次详情可查"):
            res = api.get(ep.path("material_detail", batchNo=bound["batchNo"]))
            detail = assert_ok(res, "批次详情")
            assert_fields(detail, batchNo=bound["batchNo"], orderNo=order_no)

        with report.step("查询不存在的批次，应返回 40400"):
            res = api.get(ep.path("material_detail", batchNo=f"B-NOT-EXIST-{factory.run_id}"))
            assert_rejected(res, 40400, "不存在批次")

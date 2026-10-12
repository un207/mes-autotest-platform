"""冒烟：工单主链路端到端。

一条用例走完「建单 → 派工 → 批次绑定 → 报工 → 质检 → 正反向追溯 → 关闭」，
每一步都做**双重断言**：接口返回的值要对，库里落的值也要对。
只断言接口返回是假测试 —— 接口返回 200 不代表数据真写进去了。
"""

from __future__ import annotations

import pytest

from common import report
from common.assert_helper import assert_fields, assert_ok, assert_true

pytestmark = [pytest.mark.smoke, pytest.mark.db]

PLAN_QTY = 200
REPORT_QTY = 120
QUALIFIED = 115
DEFECTIVE = 5


class TestWorkOrderLifecycle:

    @report.title("工单主链路：建单→派工→报工→质检→追溯→关闭（含落库双重断言）")
    def test_full_chain(self, api, ep, db, factory, cfg):
        order_no = None

        # ---------------------------------------------------------- 1. 创建工单
        with report.step("创建工单：状态应为 NEW，各计数归零"):
            order = factory.create_order(plan_qty=PLAN_QTY, product_name="链路冒烟件")
            order_no = order["orderNo"]
            report.attach_json("创建工单响应", order)

            assert_fields(
                order,
                status="NEW",
                planQty=PLAN_QTY,
                finishedQty=0,
                qualifiedQty=0,
                defectiveQty=0,
            )

        with report.step("[落库] 工单确实写入 mes_work_order：状态 NEW、未删除、计数为 0"):
            row = db.get_row("mes_work_order", {"order_no": order_no})
            assert row is not None, f"库里查不到刚创建的工单 {order_no} —— 接口返回成功但未落库"
            assert_true(row["status"] == "NEW", f"库中状态应为 NEW，实际 {row['status']}")
            assert_true(row["deleted"] == 0, "新建工单不应带删除标记")
            assert_true(row["finished_qty"] == 0, f"库中 finished_qty 应为 0，实际 {row['finished_qty']}")
            assert_true(row["plan_qty"] == PLAN_QTY, f"库中 plan_qty 应为 {PLAN_QTY}，实际 {row['plan_qty']}")
            assert_true(row["create_time"] is not None, "审计字段 create_time 应由框架自动填充")

        # ---------------------------------------------------------- 2. 派工
        with report.step("派工：状态应流转为 DISPATCHED，产线写入"):
            dispatched = factory.dispatch_order(order_no, line_code="L-M2")
            report.attach_json("派工响应", dispatched)
            assert_fields(dispatched, status="DISPATCHED", lineCode="L-M2")

        with report.step("[落库] 状态与产线确实更新"):
            row = db.get_row("mes_work_order", {"order_no": order_no})
            assert_true(row["status"] == "DISPATCHED", f"库中状态应为 DISPATCHED，实际 {row['status']}")
            assert_true(row["line_code"] == "L-M2", f"库中产线应为 L-M2，实际 {row['line_code']}")

        # ---------------------------------------------------------- 3. 物料批次
        with report.step("创建批次并绑定工单：状态应为 IN_USE"):
            batch = factory.create_batch(order_no=order_no, qty=PLAN_QTY)
            batch_no = batch["batchNo"]
            report.attach_json("创建批次响应", batch)
            assert_fields(batch, orderNo=order_no, status="IN_USE")

        with report.step("[落库] 批次已绑定工单，且自动落下 INBOUND 追溯节点"):
            b_row = db.get_row("mes_material_batch", {"batch_no": batch_no})
            assert b_row is not None, f"库里查不到批次 {batch_no}"
            assert_true(b_row["order_no"] == order_no, "批次应绑定到该工单")
            assert_true(b_row["status"] == "IN_USE", f"批次状态应为 IN_USE，实际 {b_row['status']}")

            nodes = db.query_all(
                "SELECT node_type, node_desc FROM mes_trace_record WHERE batch_no = %s", [batch_no]
            )
            assert_true(len(nodes) == 1, f"创建批次应落下 1 条追溯节点，实际 {len(nodes)} 条")
            assert_true(nodes[0]["node_type"] == "INBOUND", f"节点类型应为 INBOUND，实际 {nodes[0]['node_type']}")

        # ---------------------------------------------------------- 4. 报工
        with report.step(f"报工：{REPORT_QTY} 件（合格 {QUALIFIED} / 不良 {DEFECTIVE}），应流转 IN_PROGRESS"):
            reported = factory.report(
                order_no, report_qty=REPORT_QTY, qualified=QUALIFIED, defective=DEFECTIVE
            )
            report.attach_json("报工响应", reported)

            assert_fields(
                reported,
                status="IN_PROGRESS",
                finishedQty=REPORT_QTY,
                qualifiedQty=QUALIFIED,
                defectiveQty=DEFECTIVE,
            )

        with report.step("完工进度 60%、直通率 95.83% 应由服务端算准"):
            assert reported["progressRate"] == pytest.approx(REPORT_QTY / PLAN_QTY * 100, abs=0.01), (
                f"完工进度应为 {REPORT_QTY / PLAN_QTY * 100}%，实际 {reported['progressRate']}"
            )
            assert reported["yieldRate"] == pytest.approx(QUALIFIED / REPORT_QTY * 100, abs=0.01), (
                f"直通率应为 {QUALIFIED / REPORT_QTY * 100}%，实际 {reported['yieldRate']}"
            )

        with report.step("首次报工应记录实际开工时间"):
            assert_true(reported.get("actualStartTime"), "首次报工应把 actualStartTime 填上（计划与实际工期的起点）")

        with report.step("[落库] 工单累计计数已更新，且报工记录单独落表"):
            row = db.get_row("mes_work_order", {"order_no": order_no})
            assert_true(row["finished_qty"] == REPORT_QTY, f"库中 finished_qty 应为 {REPORT_QTY}，实际 {row['finished_qty']}")
            assert_true(row["qualified_qty"] == QUALIFIED, f"库中 qualified_qty 应为 {QUALIFIED}，实际 {row['qualified_qty']}")
            assert_true(row["defective_qty"] == DEFECTIVE, f"库中 defective_qty 应为 {DEFECTIVE}，实际 {row['defective_qty']}")
            assert_true(row["status"] == "IN_PROGRESS", f"库中状态应为 IN_PROGRESS，实际 {row['status']}")

            assert_true(
                db.count("mes_work_report", {"order_no": order_no}) == 1,
                "应恰好落下 1 条报工记录",
            )
            r_row = db.query_one("SELECT * FROM mes_work_report WHERE order_no = %s", [order_no])
            assert_true(r_row["report_qty"] == REPORT_QTY, "报工记录中的数量应为本次报工数，而非累计数")
            assert_true(r_row["qualified_qty"] + r_row["defective_qty"] == r_row["report_qty"], "落库后数量仍应守恒")

        with report.step("[落库] 报工应驱动产生 PRODUCE 追溯节点"):
            produce = db.query_all(
                "SELECT * FROM mes_trace_record WHERE order_no = %s AND node_type = 'PRODUCE'", [order_no]
            )
            assert_true(len(produce) == 1, f"报工应落下 1 条 PRODUCE 节点，实际 {len(produce)} 条")

        # ---------------------------------------------------------- 5. 质检
        with report.step("录入质检：不良 2 件，结论应由系统推导为 FAIL"):
            res = api.post(
                ep.path("quality_inspections"),
                json_body={
                    "orderNo": order_no,
                    "batchNo": batch_no,
                    "inspectType": "IPQC",
                    "inspectQty": 10,
                    "qualifiedQty": 8,
                    "defectiveQty": 2,
                    "defectCode": "D-M2-尺寸超差",
                    "inspector": f"{factory.run_id}-QC",
                },
            )
            qc = assert_ok(res, "录入质检")
            report.attach_json("质检响应", qc)
            assert_fields(qc, result="FAIL", defectCode="D-M2-尺寸超差", qualifiedQty=8, defectiveQty=2)

        with report.step("[落库] 质检记录落表，并产生 INSPECT 追溯节点"):
            assert_true(db.count("mes_quality_inspection", {"order_no": order_no}) == 1, "应落下 1 条质检记录")
            inspect_nodes = db.query_all(
                "SELECT * FROM mes_trace_record WHERE order_no = %s AND node_type = 'INSPECT'", [order_no]
            )
            assert_true(len(inspect_nodes) == 1, f"质检应落下 1 条 INSPECT 节点，实际 {len(inspect_nodes)} 条")

        # ---------------------------------------------------------- 6. 双向追溯
        with report.step("反向追溯（工单→全部信息）：1 个批次 / 3 个节点 / 1 条不良"):
            trace = assert_ok(api.get(ep.path("trace_by_order", orderNo=order_no)), "反向追溯")
            report.attach_json("反向追溯响应", trace)

            assert_true(len(trace["batches"]) == 1, f"应关联 1 个批次，实际 {len(trace['batches'])}")
            assert_true(len(trace["nodes"]) == 3, f"应有 3 个节点（入库+投产+检验），实际 {len(trace['nodes'])}")
            assert_true(len(trace["defects"]) == 1, f"应有 1 条不良明细，实际 {len(trace['defects'])}")
            assert_true(trace["order"]["orderNo"] == order_no, "追溯结果应指向该工单")

            node_types = [n["nodeType"] for n in trace["nodes"]]
            assert_true(
                node_types == ["INBOUND", "PRODUCE", "INSPECT"],
                f"节点顺序应体现业务先后，实际 {node_types}",
            )

        with report.step("正向追溯（批次→流向）：应能反查所绑工单"):
            batch_trace = assert_ok(api.get(ep.path("trace_by_batch", batchNo=batch_no)), "正向追溯")
            report.attach_json("正向追溯响应", batch_trace)
            assert_true(batch_trace["boundOrderNo"] == order_no, "正向追溯应反查到所绑工单")

        # ---------------------------------------------------------- 7. 关闭工单
        with report.step("关闭工单：状态 CLOSED，并记录实际完工时间"):
            res = api.put(ep.path("work_order_close", orderNo=order_no), json_body={"remark": "链路冒烟收尾"})
            closed = assert_ok(res, "关闭工单")
            report.attach_json("关闭响应", closed)
            assert_fields(closed, status="CLOSED")
            assert_true(closed.get("actualEndTime"), "关闭时应记录实际完工时间")

        with report.step("[落库] 关闭状态与实际完工时间已持久化"):
            row = db.get_row("mes_work_order", {"order_no": order_no})
            assert_true(row["status"] == "CLOSED", f"库中状态应为 CLOSED，实际 {row['status']}")
            assert_true(row["actual_end_time"] is not None, "库中 actual_end_time 不应为空")

        # ---------------------------------------------------------- 8. 详情与报工明细
        with report.step("工单详情应带出报工明细"):
            detail = assert_ok(api.get(ep.path("work_order_detail", orderNo=order_no)), "工单详情")
            assert_true(len(detail["reports"]) == 1, f"应带出 1 条报工明细，实际 {len(detail['reports'])}")
            assert_true(
                detail["reports"][0]["reportQty"] == REPORT_QTY,
                "报工明细里的数量应为本次报工数",
            )

        with report.step("[落库] 全链路结束后，该工单相关数据行数与预期一致"):
            expected = {
                "mes_work_report": 1,
                "mes_quality_inspection": 1,
                "mes_material_batch": 1,
            }
            for table, want in expected.items():
                got = db.count(table, {"order_no": order_no})
                assert_true(got == want, f"{table} 应有 {want} 行，实际 {got} 行")

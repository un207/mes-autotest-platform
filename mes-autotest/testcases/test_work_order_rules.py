"""回归：工单业务规则。

覆盖 M1 里落地的全部规则分支，用例数据来自 data/work_order_rules.yml 与 data/work_order_param.yml。
新增规则分支时只需往 YAML 里加一条，不用改本文件 —— 这是数据驱动的意义。
"""

from __future__ import annotations

import pytest

from common import report
from common.assert_helper import assert_fields, assert_ok, assert_rejected, assert_true
from common.config_loader import load_cases

RULES = load_cases("work_order_rules")
PARAMS = load_cases("work_order_param")

pytestmark = [pytest.mark.regression]


# ---------------------------------------------------------------------------
# 测试辅助
# ---------------------------------------------------------------------------

def build_order_in_state(factory, api, ep, setup: str, plan_qty: int = 100) -> str:
    """把工单构造成指定状态，返回工单号。

    setup 取值：new / dispatched / in_progress / closed
    """
    order_no = factory.create_order(plan_qty=plan_qty)["orderNo"]

    if setup == "new":
        return order_no

    factory.dispatch_order(order_no)
    if setup == "dispatched":
        return order_no

    factory.report(order_no, report_qty=10, qualified=10, defective=0)
    if setup == "in_progress":
        return order_no

    if setup == "closed":
        res = api.put(ep.path("work_order_close", orderNo=order_no), json_body={"remark": "构造已关闭状态"})
        assert res.ok, f"构造 closed 状态失败\n  {res.describe()}"
        return order_no

    raise ValueError(f"未知的 setup 取值: {setup}")


def register_if_created(res, factory) -> None:
    """裸调接口造数的用例专用兜底：万一请求意外成功了，把新单号登记进清场清单。

    负向用例本不该造出数据，但真出现「本该被拒绝却通过」时，最怕的是又留一条垃圾数据
    干扰后续排查 —— 登记一下，清场照样兜得住。
    """
    if res.ok and isinstance(res.data, dict) and res.data.get("orderNo"):
        factory.register_order(res.data["orderNo"])


def perform_action(api, ep, factory, order_no: str, action: str):
    """在既有工单上执行一个动作，返回接口结果。"""
    if action == "report":
        return api.post(
            ep.path("work_order_reports", orderNo=order_no),
            json_body={"reportQty": 1, "worker": f"{factory.run_id}-ACT"},
        )
    if action == "close":
        return api.put(ep.path("work_order_close", orderNo=order_no), json_body={"remark": "状态机用例"})
    if action == "dispatch":
        return api.put(
            ep.path("work_order_dispatch", orderNo=order_no),
            json_body={"lineCode": "L-M2-AGAIN"},
        )
    raise ValueError(f"未知的 action 取值: {action}")


# ---------------------------------------------------------------------------
# 数量守恒
# ---------------------------------------------------------------------------

class TestQtyConservation:

    @pytest.mark.parametrize("case", RULES["qty_conservation"], ids=lambda c: c["id"])
    @report.title("数量守恒：合格数 + 不良数 必须等于报工数")
    def test_illegal_quantity_combination_rejected(self, api, ep, factory, case):
        order_no = build_order_in_state(factory, api, ep, "dispatched", case["plan_qty"])

        body = {"reportQty": case["report_qty"], "worker": f"{factory.run_id}-QTY"}
        if case.get("qualified") is not None:
            body["qualifiedQty"] = case["qualified"]
        if case.get("defective") is not None:
            body["defectiveQty"] = case["defective"]

        with report.step(f"场景：{case['desc']}"):
            res = api.post(ep.path("work_order_reports", orderNo=order_no), json_body=body)
            report.attach_json("请求体", body)
            report.attach_json("响应", res.raw_text)

        with report.step(f"断言被拒绝，业务码 {case['expect_code']}"):
            assert_rejected(res, case["expect_code"], case["desc"])


class TestQtyDerive:

    @pytest.mark.parametrize("case", RULES["qty_derive"], ids=lambda c: c["id"])
    @report.title("数量推算：只传一个或都不传时的推导规则")
    def test_missing_quantity_is_derived(self, api, ep, factory, case):
        order_no = build_order_in_state(factory, api, ep, "dispatched", case["plan_qty"])

        body = {"reportQty": case["report_qty"], "worker": f"{factory.run_id}-DERIVE"}
        if case.get("qualified") is not None:
            body["qualifiedQty"] = case["qualified"]
        if case.get("defective") is not None:
            body["defectiveQty"] = case["defective"]

        with report.step(f"场景：{case['desc']}"):
            res = api.post(ep.path("work_order_reports", orderNo=order_no), json_body=body)
            data = assert_ok(res, case["desc"])
            report.attach_json("报工响应", data)

        with report.step("断言推算结果正确，且数量仍然守恒"):
            assert_fields(
                data,
                qualifiedQty=case["expect_qualified"],
                defectiveQty=case["expect_defective"],
            )
            assert_true(
                data["qualifiedQty"] + data["defectiveQty"] == case["report_qty"],
                "推算后仍应满足：合格 + 不良 = 报工",
            )


# ---------------------------------------------------------------------------
# 超报拦截
# ---------------------------------------------------------------------------

class TestOverProduction:

    @pytest.mark.parametrize("case", RULES["over_production"], ids=lambda c: c["id"])
    @report.title("超报拦截：累计报工数不得超过计划数")
    def test_cumulative_report_must_not_exceed_plan(self, api, ep, factory, case):
        order_no = build_order_in_state(factory, api, ep, case["setup"], case["plan_qty"])

        with report.step("构造前置：先报一次工"):
            if case.get("first_report"):
                factory.report(
                    order_no,
                    report_qty=case["first_report"],
                    qualified=case["first_report"],
                    defective=0,
                )

        with report.step(f"场景：{case['desc']}"):
            res = api.post(
                ep.path("work_order_reports", orderNo=order_no),
                json_body={
                    "reportQty": case["report_qty"],
                    "qualifiedQty": case["qualified"],
                    "defectiveQty": case["defective"],
                    "worker": f"{factory.run_id}-OVER",
                },
            )
            report.attach_json("响应", res.raw_text)

        with report.step(f"断言业务码为 {case['expect_code']}"):
            if case["expect_code"] == 0:
                data = assert_ok(res, case["desc"])
                expected_total = (case.get("first_report") or 0) + case["report_qty"]
                assert_true(
                    data["finishedQty"] == expected_total,
                    f"累计报工应为 {expected_total}，实际 {data['finishedQty']}",
                )
            else:
                assert_rejected(res, case["expect_code"], case["desc"])


# ---------------------------------------------------------------------------
# 状态机
# ---------------------------------------------------------------------------

class TestStateMachine:

    @pytest.mark.parametrize("case", RULES["state_machine"], ids=lambda c: c["id"])
    @report.title("工单状态机：非法流转必须被拦截")
    def test_state_transition(self, api, ep, factory, case):
        with report.step(f"构造工单状态：{case['setup']}"):
            order_no = build_order_in_state(factory, api, ep, case["setup"], 100)

        with report.step(f"场景：在 {case['setup']} 状态执行 {case['action']} —— {case['desc']}"):
            res = perform_action(api, ep, factory, order_no, case["action"])
            report.attach_json("响应", res.raw_text)

        with report.step(f"断言业务码为 {case['expect_code']}"):
            if case["expect_code"] == 0:
                assert_ok(res, case["desc"])
            else:
                assert_rejected(res, case["expect_code"], case["desc"])


# ---------------------------------------------------------------------------
# 计划时间与参数校验
# ---------------------------------------------------------------------------

class TestPlanTime:

    @pytest.mark.parametrize("case", RULES["plan_time_reject"], ids=lambda c: c["id"])
    @report.title("计划时间校验：结束不得早于开始")
    def test_plan_end_before_start_rejected(self, api, ep, factory, case):
        with report.step(f"场景：{case['desc']}"):
            res = api.post(
                ep.path("work_orders"),
                json_body={
                    "productCode": factory.unique("P"),
                    "productName": "计划时间校验件",
                    "planQty": 10,
                    "planStartTime": case["plan_start"],
                    "planEndTime": case["plan_end"],
                },
            )
            report.attach_json("响应", res.raw_text)
            register_if_created(res, factory)

        with report.step(f"断言被拒绝，业务码 {case['expect_code']}"):
            assert_rejected(res, case["expect_code"], case["desc"])


class TestParamValidation:

    @pytest.mark.parametrize("case", PARAMS["create_order_reject"], ids=lambda c: c["id"])
    @report.title("参数校验：创建工单必填项与取值范围")
    def test_create_order_param_rejected(self, api, ep, factory, case):
        body = dict(case["body"])
        # 未显式指定产品编码的用例，补一个唯一编码避免撞唯一键
        if "productCode" not in body:
            body["productCode"] = factory.unique("P")

        # 超长字段：按声明的片段与最小长度生成，并当场校验生成结果确实够长，
        # 否则用例会「假通过」——请求没被拒只因为字段其实没超长。
        if case.get("long_field"):
            unit = case["repeat_unit"]
            need = case["min_length"]
            times = -(-need // len(unit))
            value = unit * times
            assert_true(
                len(value) >= need,
                f"用例数据有误：为 {case['long_field']} 生成的字符串长度 {len(value)} 未达到 {need}",
            )
            body[case["long_field"]] = value

        with report.step(f"场景：{case['desc']}"):
            res = api.post(ep.path("work_orders"), json_body=body)
            report.attach_json("请求体", body)
            report.attach_json("响应", res.raw_text)
            register_if_created(res, factory)

        with report.step(f"断言被拒绝，业务码 {case['expect_code']}"):
            assert_rejected(res, case["expect_code"], case["desc"])

    @pytest.mark.parametrize("case", PARAMS["report_reject"], ids=lambda c: c["id"])
    @report.title("参数校验：报工必填项与取值范围")
    def test_report_param_rejected(self, api, ep, factory, case):
        order_no = build_order_in_state(factory, api, ep, "dispatched", 100)

        with report.step(f"场景：{case['desc']}"):
            res = api.post(ep.path("work_order_reports", orderNo=order_no), json_body=case["body"])
            report.attach_json("请求体", case["body"])
            report.attach_json("响应", res.raw_text)

        with report.step(f"断言被拒绝，业务码 {case['expect_code']}"):
            assert_rejected(res, case["expect_code"], case["desc"])

    @report.title("不存在的工单：查询与写入都应返回 40400")
    def test_not_exist_order(self, api, ep, factory):
        ghost = f"WO-NOT-EXIST-{factory.run_id}"

        with report.step("查询不存在的工单"):
            res = api.get(ep.path("work_order_detail", orderNo=ghost))
            report.attach_json("响应", res.raw_text)
            assert_rejected(res, 40400, "查询不存在工单")

        with report.step("对不存在的工单报工"):
            res = api.post(
                ep.path("work_order_reports", orderNo=ghost),
                json_body={"reportQty": 10, "worker": f"{factory.run_id}-GHOST"},
            )
            report.attach_json("响应", res.raw_text)
            assert_rejected(res, 40400, "写入不存在工单")

    @report.title("请求体非法 JSON：应返回 40001 而不是 500")
    def test_malformed_json_body(self, api, ep):
        with report.step("发送结构非法的 JSON 字符串"):
            res = api.call("POST", ep.path("work_orders"), json_body="这不是合法 JSON 结构")
            report.attach_json("响应", res.raw_text)

        with report.step("断言返回参数类错误码，而非系统错误"):
            assert_true(
                res.code in (40001, 40000),
                f"非法请求体应归为参数错误(40001/40000)，实际 code={res.code} message={res.message!r}",
            )
            assert_true(res.code != 50000, "不应把参数错误兜底成系统内部错误")

    @report.title("分页参数越界：pageSize 超过上限应被拒绝")
    def test_page_size_over_limit(self, api, ep):
        with report.step("pageSize=201（上限 200）"):
            res = api.get(ep.path("work_orders"), params={"pageNum": 1, "pageSize": 201})
            report.attach_json("响应", res.raw_text)

        with report.step("断言被拒绝"):
            assert_rejected(res, 40000, "pageSize 越界")

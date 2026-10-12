"""回归：设备数采质量判定。

数采入口是脏数据进入 MES 的唯一通道，三层把关（可解析性 → 工况区间 → 时间合理性）
必须逐层验证。要点是：脏数据不静默丢弃，一律留痕。
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from common import report
from common.assert_helper import assert_ok, assert_rejected, assert_true
from common.config_loader import load_cases

CASES = load_cases("device_data_rules")

pytestmark = [pytest.mark.regression, pytest.mark.db]


def post_device_data(api, ep, factory, metric, raw, equipment=None, **extra):
    """上报一条设备数据。"""
    body = {
        "equipmentCode": equipment or factory.equipment_code(),
        "lineCode": "L-M2",
        "metric": metric,
        "rawValue": raw,
        **extra,
    }
    res = api.post(ep.path("device_data"), json_body=body)
    report.attach_json("上报请求体", body)
    return res


class TestQualityJudgement:

    @pytest.mark.parametrize("case", CASES["quality_cases"], ids=lambda c: c["id"])
    @report.title("数采三层关口：可解析性 / 工况区间 / 时间合理性")
    def test_quality_flag(self, api, ep, db, factory, case):
        with report.step(f"场景：{case['desc']}（{case['metric']} = {case['raw']!r}）"):
            res = post_device_data(api, ep, factory, case["metric"], case["raw"])
            data = assert_ok(res, case["desc"])
            report.attach_json("上报响应", data)

        with report.step(f"断言质量标记为 {case['expect_flag']}"):
            assert_true(
                data.get("qualityFlag") == case["expect_flag"],
                f"质量标记应为 {case['expect_flag']}，实际 {data.get('qualityFlag')}（原因：{data.get('qualityMessage')!r}）",
            )

        with report.step("断言数值是否入账（异常数据不入账但原始串保留）"):
            if case["value_present"]:
                assert_true(
                    data.get("metricValue") is not None,
                    "该场景应解析出数值并留档，实际 metricValue 为空",
                )
                assert_true(
                    float(data["metricValue"]) == float(case["raw"]),
                    f"解析值应等于原始值，实际 {data['metricValue']} vs {case['raw']}",
                )
            else:
                assert_true(
                    data.get("metricValue") is None,
                    f"解析失败时 metricValue 应为空，实际 {data['metricValue']}",
                )

        with report.step("断言原始上报串永远保留（事后可查设备到底发了什么）"):
            assert_true(
                data.get("rawValue") == case["raw"],
                f"原始值应原样保留，实际 {data.get('rawValue')!r}",
            )

        with report.step("[落库] 质量标记与数值落库一致"):
            row = db.get_row("mes_device_data", {"id": data["id"]})
            assert_true(row is not None, "库里查不到刚上报的数据")
            assert_true(row["quality_flag"] == case["expect_flag"], f"库中质量标记应为 {case['expect_flag']}，实际 {row['quality_flag']}")
            assert_true(row["raw_value"] == case["raw"], "库中原始值应与上报一致")
            if case["value_present"]:
                assert_true(row["metric_value"] is not None, "库中数值应不为空")
            else:
                assert_true(row["metric_value"] is None, "库中数值应为空")
                assert_true(row["quality_message"], "异常数据应记录原因说明")

    @report.title("时间合理性：采集时间超前过多应判可疑")
    def test_future_collect_time_is_suspect(self, api, ep, db, factory):
        future = (datetime.now() + timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
        equipment = factory.equipment_code()

        with report.step(f"上报采集时间为 2 小时后的数据（{future}）"):
            res = post_device_data(api, ep, factory, "TEMPERATURE", "30",
                                   equipment=equipment, collectTime=future)
            data = assert_ok(res, "未来时间上报")
            report.attach_json("上报响应", data)

        with report.step("断言判为可疑，并给出时钟异常提示"):
            assert_true(data.get("qualityFlag") == "SUSPECT", f"应判可疑，实际 {data['qualityFlag']}")
            assert_true(
                "时间" in (data.get("qualityMessage") or ""),
                f"异常原因应指向采集时间，实际 {data.get('qualityMessage')!r}",
            )

    @report.title("时间合理性：采集时间在容忍范围内应判正常")
    def test_slightly_future_collect_time_is_ok(self, api, ep, factory):
        # 容忍阈值是 5 分钟，取 1 分钟后应仍判正常
        near_future = (datetime.now() + timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M:%S")

        with report.step(f"上报采集时间为 1 分钟后（{near_future}），应判正常"):
            res = post_device_data(api, ep, factory, "TEMPERATURE", "30", collectTime=near_future)
            data = assert_ok(res, "轻微超前上报")
            assert_true(data.get("qualityFlag") == "OK", f"容忍范围内应判正常，实际 {data['qualityFlag']}")


class TestBatchReport:

    @pytest.mark.parametrize("case", CASES["batch_cases"], ids=lambda c: c["id"])
    @report.title("批量上报：条数边界")
    def test_batch_report(self, api, ep, factory, case):
        equipment = factory.equipment_code()
        payload = [
            {"equipmentCode": equipment, "lineCode": "L-M2", "metric": "OUTPUT", "rawValue": str(100 + i)}
            for i in range(case["size"])
        ]

        with report.step(f"场景：{case['desc']}（{case['size']} 条）"):
            res = api.post(ep.path("device_data_batch"), json_body=payload)
            report.attach_json("响应摘要", {"code": res.code, "message": res.message})

        with report.step(f"断言业务码为 {case['expect_code']}"):
            if case["expect_code"] == 0:
                data = assert_ok(res, case["desc"])
                assert_true(len(data) == case["size"], f"入库条数应为 {case['size']}，实际 {len(data)} 条")
            else:
                assert_rejected(res, case["expect_code"], case["desc"])

    @report.title("批量上报：空列表应被拒绝")
    def test_batch_empty_rejected(self, api, ep):
        with report.step("提交空列表"):
            res = api.post(ep.path("device_data_batch"), json_body=[])
            report.attach_json("响应", res.raw_text)

        with report.step("断言被拒绝而不是静默成功"):
            assert_rejected(res, 40000, "空批量上报")


class TestDeviceParamValidation:

    @report.title("数采参数校验：必填项与枚举取值")
    def test_param_validation(self, api, ep, factory):
        equipment = factory.equipment_code()

        with report.step("缺设备编号，应拒绝"):
            res = api.post(
                ep.path("device_data"),
                json_body={"metric": "OUTPUT", "rawValue": "10"},
            )
            assert_rejected(res, 40000, "缺设备编号")

        with report.step("缺指标类型，应拒绝"):
            res = api.post(
                ep.path("device_data"),
                json_body={"equipmentCode": equipment, "rawValue": "10"},
            )
            assert_rejected(res, 40000, "缺指标类型")

        with report.step("缺上报值，应拒绝（rawValue 是 @NotBlank，空串同样拒绝）"):
            res = api.post(
                ep.path("device_data"),
                json_body={"equipmentCode": equipment, "metric": "OUTPUT"},
            )
            assert_rejected(res, 40000, "缺上报值")

        with report.step("指标类型取值非法，应拒绝（枚举无法反序列化 → 归为请求体错误 40001）"):
            res = api.post(
                ep.path("device_data"),
                json_body={"equipmentCode": equipment, "metric": "NOT_A_METRIC", "rawValue": "10"},
            )
            report.attach_json("响应", res.raw_text)
            assert_rejected(res, 40001, "非法枚举取值")

        with report.step("上报值超长（>64 字符），应拒绝"):
            res = api.post(
                ep.path("device_data"),
                json_body={"equipmentCode": equipment, "metric": "OUTPUT", "rawValue": "9" * 65},
            )
            assert_rejected(res, 40000, "上报值超长")


class TestDeviceQuery:

    @report.title("数采查询：按质量标记筛选、异常数据可捞取")
    def test_query_and_abnormal(self, api, ep, db, factory):
        equipment = factory.equipment_code()

        with report.step("同一设备上报三条：正常、可疑、异常"):
            assert_ok(post_device_data(api, ep, factory, "OUTPUT", "100", equipment=equipment), "正常数据")
            assert_ok(post_device_data(api, ep, factory, "TEMPERATURE", "512", equipment=equipment), "可疑数据")
            assert_ok(post_device_data(api, ep, factory, "STATUS", "###", equipment=equipment), "异常数据")

        with report.step("按设备编号筛选，应命中 3 条"):
            res = api.get(ep.path("device_data"), params={"equipmentCode": equipment, "pageSize": 50})
            page = assert_ok(res, "数采分页")
            report.attach_json("分页结果", page)
            assert_true(page["total"] == 3, f"应命中 3 条，实际 {page['total']}")

        with report.step("按 qualityFlag=SUSPECT 筛选，应命中 1 条"):
            res = api.get(
                ep.path("device_data"),
                params={"equipmentCode": equipment, "qualityFlag": "SUSPECT", "pageSize": 50},
            )
            page = assert_ok(res, "按质量标记筛选")
            assert_true(page["total"] == 1, f"可疑数据应为 1 条，实际 {page['total']}")

        with report.step("异常数据接口应能捞到本轮造的可疑与异常数据"):
            res = api.get(ep.path("device_data_abnormal"), params={"limit": 200})
            rows = assert_ok(res, "异常数据列表")
            report.attach_json("异常数据条数", len(rows))

            mine = [r for r in rows if r["equipmentCode"] == equipment]
            assert_true(
                len(mine) == 2,
                f"本轮该设备应有 2 条非正常数据（1 可疑 + 1 异常），实际 {len(mine)}",
            )
            flags = sorted(r["qualityFlag"] for r in mine)
            assert_true(flags == ["BAD", "SUSPECT"], f"质量标记应为 BAD 与 SUSPECT，实际 {flags}")

        with report.step("[落库] 三条数据均真实落表，未被静默丢弃"):
            assert_true(
                db.count("mes_device_data", {"equipment_code": equipment}) == 3,
                "三条上报都应落库——脏数据也必须留痕",
            )

    @report.title("异常数据查询：limit 越界应被拒绝")
    def test_abnormal_limit_validation(self, api, ep):
        with report.step("limit=0，低于下界"):
            res = api.get(ep.path("device_data_abnormal"), params={"limit": 0})
            assert_rejected(res, 40000, "limit 下界")

        with report.step("limit=201，高于上界 200"):
            res = api.get(ep.path("device_data_abnormal"), params={"limit": 201})
            assert_rejected(res, 40000, "limit 上界")

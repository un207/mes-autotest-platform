"""冒烟：服务自检接口。

CI 每次提交先跑这一组，确认「服务起得来、库连得上」再往下跑业务用例。
"""

from __future__ import annotations

import pytest

from common import report
from common.assert_helper import assert_fields, assert_ok

pytestmark = [pytest.mark.smoke]


class TestHealth:

    @report.title("存活检查：服务进程可用")
    def test_health_returns_up(self, api, ep):
        res = api.get(ep.path("health"))

        with report.step("断言 HTTP 200 且业务码为 0"):
            data = assert_ok(res, "存活检查")
            report.attach_json("存活检查响应", res.data)

        with report.step("断言关键字段"):
            assert_fields(data, service="mes-platform", status="UP")

    @report.title("就绪检查：数据库连通")
    def test_ready_reports_database_up(self, api, ep, db):
        res = api.get(ep.path("ready"))

        with report.step("断言就绪且数据库 UP"):
            data = assert_ok(res, "就绪检查")
            report.attach_json("就绪检查响应", res.data)
            assert_fields(data, database="UP", status="UP")

        with report.step("交叉校验：接口上报的库版本应与直连取到的一致"):
            db_version = db.ping()
            assert db_version, "直连测试库取版本号失败"
            assert data.get("dbProduct") == db_version, (
                f"接口上报库版本 {data.get('dbProduct')!r} 与直连取到 {db_version!r} 不一致 —— "
                f"通常说明 MES 服务连的不是测试库，落库校验会全部失准"
            )

    @report.title("未知路由：返回 404 且响应结构同构")
    def test_unknown_route_returns_404(self, api):
        res = api.get("/api/this-endpoint-does-not-exist")

        with report.step("断言 HTTP 404 与业务码 40400"):
            from common.assert_helper import assert_not_found_route

            assert_not_found_route(res, "未知路由")

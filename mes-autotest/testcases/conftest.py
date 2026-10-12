"""pytest 全局夹具与前置检查。

前置检查刻意做成「失败即停」而不是「让几十个用例一起报错」：
环境不通（服务没起 / 库连不上）时，给一条能照着做的提示，比刷屏的失败堆栈有用得多。
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest

# 让 testcases/ 下的模块能直接 import common.*
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common import history  # noqa: E402
from common.config_loader import load_config, load_endpoints  # noqa: E402
from common.data_factory import DataFactory  # noqa: E402
from common.db_client import DbClient  # noqa: E402
from common.http_client import ApiClient  # noqa: E402

_CLEANUP_REPORT: dict[str, int] = {}
_SWEEP_REPORT: dict[str, int] = {}
_SESSION_START: float = 0.0

# 统计与记录跨 hook 传递。不用 pytest.Config.stash 是因为这里只需要单进程顺序执行；
# 本工程不支持 xdist 并发（清场的时间窗兜底基于顺序假设），故无并发写风险。
_LAST_RECORD: dict = {}


@pytest.fixture(scope="session")
def cfg() -> dict:
    return load_config()


@pytest.fixture(scope="session")
def ep():
    return load_endpoints()


@pytest.fixture(scope="session")
def api(cfg: dict) -> ApiClient:
    """接口客户端。服务不可达时直接终止本轮，并给出启动指引。"""
    client = ApiClient(
        base_url=cfg["api"]["base_url"],
        timeout=cfg["api"]["timeout"],
        verbose=cfg["api"].get("verbose", False),
    )

    if not client.is_reachable():
        client.close()
        pytest.exit(
            "\n"
            "============================================================\n"
            " MES 服务不可达，测试无法开始\n"
            f"   base_url = {cfg['api']['base_url']}\n"
            "------------------------------------------------------------\n"
            " 请先在 mes-platform 目录下按测试 profile 启动服务：\n"
            "   unset SERVER__PORT SERVER__HOST\n"
            '   export JAVA_HOME="C:/Users/Administrator/.jdks/temurin-17.0.20.1"\n'
            "   export MES_PROFILE=test\n"
            "   mvn spring-boot:run\n"
            " 测试 profile 会把数据写进 mes_test，与业务库隔离。\n"
            "============================================================\n",
            returncode=2,
        )

    yield client
    client.close()


@pytest.fixture(scope="session")
def db(cfg: dict) -> DbClient:
    """测试库客户端。落库校验与清场都走它。"""
    client = DbClient(**cfg["db"])
    version = client.ping()

    if version is None:
        pytest.exit(
            "\n"
            "============================================================\n"
            " 测试库连接失败，落库校验类用例无法执行\n"
            f"   {cfg['db']['user']}@{cfg['db']['host']}:{cfg['db']['port']}"
            f"/{cfg['db']['database']}\n"
            "------------------------------------------------------------\n"
            " 请确认：1) MySQL 已启动；2) 口令正确（可用 MES_DB_PASSWORD 覆盖）；\n"
            "         3) 已执行 sql/01_create_database.sql 与 sql/03_schema_mes_test.sql\n"
            "============================================================\n",
            returncode=2,
        )

    yield client


@pytest.fixture(scope="session")
def factory(api: ApiClient, ep, db: DbClient, cfg: dict) -> DataFactory:
    """造数工厂。用例结束后统一清场，无论成功失败都会执行。"""
    guard_database_name(cfg)

    f = DataFactory(api=api, ep=ep, db=db, prefix=cfg["run"]["data_prefix"])
    yield f

    if cfg["run"]["cleanup"]:
        try:
            _CLEANUP_REPORT.update(f.cleanup())
            _SWEEP_REPORT["swept"] = f.swept
        except AssertionError as exc:
            print(f"\n[清场] 已跳过：{exc}")
    else:
        print("\n[清场] 配置中 cleanup=false，本轮数据保留在库中以便排查")


# 不参与探针定位的系统库
_SYSTEM_SCHEMAS = {"information_schema", "mysql", "performance_schema", "sys"}


def _locate_and_purge_probe(db: DbClient, order_no: str, validation_db: str) -> str | None:
    """探针工单若落在别的库，定位它并从那里删掉；返回落点库名，未找到返回 None。

    为什么必须单独处理这一步：环境不对时会话被 pytest.exit 中断，
    正常的清场流程（factory 夹具的收尾）不会执行；而框架的数据库连接指向校验库（mes_test），
    在它里面当然找不到落在业务库的探针。不处理的话，每失败一次就往业务库多留一条垃圾工单，
    积累起来会污染管理界面的列表与统计口径。

    利用「连接 A 库也能访问 B 库」这一点，用全限定名跨库操作，无需新建连接。
    创建工单只写 mes_work_order 一张表，因此删除单条即可，无需处理级联数据。
    """
    rows = db.query_all(
        "SELECT table_schema AS s FROM information_schema.tables WHERE table_name = %s",
        ("mes_work_order",),
    )

    for row in rows:
        schema = row["s"]
        # 库名来自 information_schema，仍做一次白名单式校验再拼进 SQL
        if schema in _SYSTEM_SCHEMAS or schema == validation_db:
            continue
        if not schema.replace("_", "").isalnum():
            continue

        found = db.query_scalar(
            f"SELECT COUNT(*) FROM `{schema}`.`mes_work_order` WHERE order_no = %s",
            (order_no,),
            default=0,
        )
        if found:
            db.execute(
                f"DELETE FROM `{schema}`.`mes_work_order` WHERE order_no = %s",
                (order_no,),
            )
            return schema

    return None


@pytest.fixture(scope="session", autouse=True)
def environment_guard(factory: DataFactory) -> None:
    """环境探针：确认「服务写入的库」正是「我们校验的库」。

    做法是经接口建一条工单，再去 mes_test 找它。找不到就说明两边指向不同库 ——
    这种情况下所有落库断言都会失准，还不如在开跑前就停下来。

    最常见的原因：MES 服务忘了切 test profile，仍连在业务库 mes 上。
    """
    probe = factory.create_order(plan_qty=1, product_name="环境探针工单")
    order_no = probe["orderNo"]

    if factory.db.get_row("mes_work_order", {"order_no": order_no}) is None:
        validation_db = factory.db._cfg["database"]
        leaked_into = _locate_and_purge_probe(factory.db, order_no, validation_db)

        if leaked_into:
            leak_note = (
                f"   实际落点   = {leaked_into} 库（探针已从该库清理，不留残留）\n"
            )
            cause = f"MES 服务连的是 {leaked_into} 库，而框架校验的是 {validation_db} 库。"
        else:
            leak_note = f"   实际落点   = 未找到（可能已被其他流程清理）\n"
            cause = "服务写入的库与框架校验的库不一致。"

        pytest.exit(
            "\n"
            "============================================================\n"
            " 环境校验失败：经接口建的工单，在校验库里查不到\n"
            f"   探针工单号 = {order_no}\n"
            f"   校验库     = {validation_db}\n"
            f"{leak_note}"
            "------------------------------------------------------------\n"
            f" {cause}\n"
            " 这种情况下所有落库断言都会失准，因此在开跑前终止。\n"
            "\n"
            " 【命令行启动】\n"
            "   export MES_PROFILE=test && mvn spring-boot:run\n"
            "\n"
            " 【IDEA 中启动】\n"
            "   Run → Edit Configurations → 选中启动配置\n"
            "   → Environment variables 里增加 MES_PROFILE=test → 重启服务\n"
            "   重启后控制台应出现：The following 1 profile is active: \"test\"\n"
            "============================================================\n",
            returncode=2,
        )


def guard_database_name(cfg: dict) -> None:
    """把「当前跑的是不是测试库」这件事在开跑前就摆明，防止误连业务库。"""
    name = cfg["db"]["database"]
    if not name.endswith("_test"):
        pytest.exit(
            f"\n拒绝执行：config/env.yml 中 db.database = {name!r}，不是测试库。\n"
            f"自动化用例会造数并清场，只允许指向以 _test 结尾的库（如 mes_test）。\n",
            returncode=2,
        )


def pytest_terminal_summary(terminalreporter, exitstatus, config) -> None:
    """收尾附上清场结果与趋势对比 —— 让「库清干净没」和「比上轮好了没」一眼可见。"""
    # ---- 本轮在趋势里的位置 ----
    if _LAST_RECORD:
        records = history.load_history()
        summary = history.summarize(records)
        terminalreporter.write_sep("=", "执行历史")
        terminalreporter.write_line(
            f"  本轮：{_LAST_RECORD['time']} 通过率 {_LAST_RECORD['pass_rate']}%"
            f"（{_LAST_RECORD['passed']}/{_LAST_RECORD['total']}）耗时 {_LAST_RECORD['duration']:.1f}s"
        )
        previous = records[-2] if len(records) >= 2 else None
        if previous:
            delta = round(_LAST_RECORD["pass_rate"] - previous["pass_rate"], 2)
            trend = "持平" if delta == 0 else (f"↑ 上升 {delta}%" if delta > 0 else f"↓ 下降 {abs(delta)}%")
            terminalreporter.write_line(
                f"  对比上轮（{previous['time']} {previous['pass_rate']}%）：{trend}"
            )
        terminalreporter.write_line(
            f"  累计 {summary['runs']} 轮 · 平均通过率 {summary['avg_pass_rate']}%"
            f" · 连续全绿 {summary['streak']} 轮"
        )

    # ---- 清场结果 ----
    if not _CLEANUP_REPORT:
        return
    total = sum(_CLEANUP_REPORT.values())
    terminalreporter.write_sep("=", "测试数据清场")
    for table, count in sorted(_CLEANUP_REPORT.items()):
        if count:
            terminalreporter.write_line(f"  {table:<28} 删除 {count} 行")
    terminalreporter.write_line(f"  {'合计':<26} {total} 行")
    swept = _SWEEP_REPORT.get("swept", 0)
    if swept:
        terminalreporter.write_line(
            f"  其中兜底扫描清掉 {swept} 行 —— "
            f"说明有用例绕过了造数工厂直接调接口造数，建议改为走 factory"
        )


def pytest_sessionstart(session) -> None:
    global _SESSION_START
    _SESSION_START = time.perf_counter()


def pytest_sessionfinish(session, exitstatus) -> None:
    """本轮结束后把结果摘要追加到执行历史，供通过率趋势使用。

    只在真的跑过用例时记录 —— 单纯 --collect-only 不该污染趋势。
    统计直接取 terminalreporter 已经数好的结果，不自己重数一遍（少一处出错的地方）。
    """
    reporter = session.config.pluginmanager.get_plugin("terminalreporter")
    if reporter is None:
        return

    stats = getattr(reporter, "stats", {}) or {}
    passed = len(stats.get("passed", []))
    failed = len(stats.get("failed", []))
    error = len(stats.get("error", []))
    skipped = len(stats.get("skipped", []))
    total = passed + failed + error + skipped
    if not total:
        return

    duration = (time.perf_counter() - _SESSION_START) if _SESSION_START else 0.0

    try:
        _LAST_RECORD.update(
            history.append_run(
                total=total,
                passed=passed,
                failed=failed,
                error=error,
                skipped=skipped,
                duration=duration,
                label=os.getenv("MES_RUN_LABEL", "local"),
                meta={"exitstatus": int(exitstatus)},
            )
        )
    except OSError as exc:  # 历史写入失败不该让测试结果变红
        print(f"\n[历史] 执行历史写入失败（不影响测试结论）：{exc}")


def pytest_report_header(config) -> list[str]:
    """在输出顶部给出「这是哪一轮、跑在哪」，便于对照趋势图。"""
    records = history.load_history()
    summary = history.summarize(records)
    label = os.getenv("MES_RUN_LABEL", "local")
    lines = [f"MES 接口自动化 · 执行来源={label} · 历史累计 {summary['runs']} 轮"]
    if summary["latest"]:
        latest = summary["latest"]
        lines.append(
            f"  上一轮：{latest['time']} 通过率 {latest['pass_rate']}%"
            f"（{latest['passed']}/{latest['total']}）"
        )
    return lines

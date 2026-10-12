"""数据库客户端 —— 用于「落库校验」。

接口自动化只断言 HTTP 返回是不够的：接口返回 200 不代表数据真的写进库了。
本模块直连 mes_test，让用例可以断言「接口说改了多少，库里就真的改了多少」。

安全约定：
  - 所有值一律走参数绑定（%s 占位），不做字符串拼接
  - 表名与列名无法参数化，因此对表名做白名单校验（防误传用户数据当表名）
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterable, Iterator, Sequence

import pymysql
from pymysql.cursors import DictCursor

# 允许被访问的表白名单（与 sql/02_schema_mes.sql 一致）
ALLOWED_TABLES = frozenset(
    {
        "mes_work_order",
        "mes_work_report",
        "mes_quality_inspection",
        "mes_material_batch",
        "mes_trace_record",
        "mes_device_data",
    }
)


class DbClient:
    """轻量 MySQL 客户端。每次调用即时建立短连接，避免测试进程长期持有连接。"""

    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        database: str,
        charset: str = "utf8mb4",
        connect_timeout: int = 5,
    ) -> None:
        self._cfg = dict(
            host=host,
            port=int(port),
            user=user,
            password=password,
            database=database,
            charset=charset,
            connect_timeout=connect_timeout,
            cursorclass=DictCursor,
            autocommit=True,
        )

    # ------------------------------------------------------------------ 连接

    @contextmanager
    def _cursor(self) -> Iterator[DictCursor]:
        try:
            conn = pymysql.connect(**self._cfg)
        except pymysql.Error as exc:
            raise AssertionError(
                f"连接测试库失败：{self._cfg['host']}:{self._cfg['port']}/{self._cfg['database']} —— {exc}\n"
                f"提示：确认 MySQL 已启动、口令正确，且该库已执行 sql/01_create_database.sql 与 03_schema_mes_test.sql。"
            ) from exc
        try:
            with conn.cursor() as cur:
                yield cur
        finally:
            conn.close()

    def ping(self) -> str | None:
        """连通性探测，返回数据库版本号；连不上返回 None。"""
        try:
            rows = self.query_all("SELECT VERSION() AS v")
            return rows[0]["v"] if rows else None
        except AssertionError:
            return None

    # ------------------------------------------------------------------ 查询

    def query_all(self, sql: str, params: Sequence[Any] | None = None) -> list[dict[str, Any]]:
        with self._cursor() as cur:
            cur.execute(sql, params)
            return list(cur.fetchall())

    def query_one(self, sql: str, params: Sequence[Any] | None = None) -> dict[str, Any] | None:
        with self._cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchone()

    def query_scalar(self, sql: str, params: Sequence[Any] | None = None, default: Any = None) -> Any:
        row = self.query_one(sql, params)
        if not row:
            return default
        return next(iter(row.values()))

    # ------------------------------------------------------------------ 便捷表操作

    @staticmethod
    def _check_table(table: str) -> str:
        if table not in ALLOWED_TABLES:
            raise ValueError(f"表名不在白名单内，拒绝访问: {table}")
        return f"`{table}`"

    def get_row(self, table: str, where: dict[str, Any], columns: str = "*") -> dict[str, Any] | None:
        tbl = self._check_table(table)
        clause = " AND ".join(f"`{k}` = %s" for k in where)
        sql = f"SELECT {columns} FROM {tbl} WHERE {clause} LIMIT 1"
        return self.query_one(sql, list(where.values()))

    def count(self, table: str, where: dict[str, Any] | None = None) -> int:
        tbl = self._check_table(table)
        if where:
            clause = " AND ".join(f"`{k}` = %s" for k in where)
            sql = f"SELECT COUNT(*) AS c FROM {tbl} WHERE {clause}"
            return int(self.query_scalar(sql, list(where.values()), default=0))
        return int(self.query_scalar(f"SELECT COUNT(*) AS c FROM {tbl}", default=0))

    # ------------------------------------------------------------------ 写入

    def execute(self, sql: str, params: Sequence[Any] | None = None) -> int:
        """执行一条写语句，返回影响行数。

        仅用于测试造景（例如把批次直接置为冻结状态，好验证「冻结批次不可出货」）。
        生产代码不应通过本方法改数据。
        """
        with self._cursor() as cur:
            return cur.execute(sql, params)

    # ------------------------------------------------------------------ 清理

    def delete_in(self, table: str, column: str, values: Iterable[Any]) -> int:
        """按列批量删除（仅用于测试库清场）。values 为空时不做任何事，避免拼出无 WHERE 的 DELETE。"""
        value_list = [v for v in values if v is not None]
        if not value_list:
            return 0
        tbl = self._check_table(table)
        placeholders = ", ".join(["%s"] * len(value_list))
        sql = f"DELETE FROM {tbl} WHERE `{column}` IN ({placeholders})"
        with self._cursor() as cur:
            return cur.execute(sql, value_list)

    def delete_like(self, table: str, column: str, pattern: str) -> int:
        """按 LIKE 批量删除（仅用于测试库清场）。"""
        tbl = self._check_table(table)
        sql = f"DELETE FROM {tbl} WHERE `{column}` LIKE %s"
        with self._cursor() as cur:
            return cur.execute(sql, [pattern])

    def delete_since(self, table: str, since: Any) -> int:
        """删除 create_time 不早于指定时刻的行（仅用于测试库兜底清场）。

        用途：清掉那些绕过造数工厂、直接调接口造出来的数据 —— 它们没有登记单号，
        只能按「本轮开始之后创建」这个时间窗识别。
        """
        tbl = self._check_table(table)
        sql = f"DELETE FROM {tbl} WHERE create_time >= %s"
        with self._cursor() as cur:
            return cur.execute(sql, [since])

    def truncate(self, table: str) -> None:
        """清空整表（仅用于测试库重置，调用前请确认目标库是 mes_test）。"""
        tbl = self._check_table(table)
        with self._cursor() as cur:
            cur.execute(f"TRUNCATE TABLE {tbl}")

    def ensure_test_database(self) -> None:
        """安全护栏：确认当前连的是测试库，防止误删业务库数据。"""
        name = self._cfg["database"]
        if not name.endswith("_test"):
            raise AssertionError(
                f"当前连接的库是 [{name}]，不是测试库。清理操作已阻止 —— "
                f"请把 config/env.yml 的 db.database 指向 mes_test。"
            )

"""测试数据工厂 —— 造数与清场。

两个硬要求：
  1. **可重复**：每轮用例生成的编码都带本轮唯一前缀，反复跑不会撞唯一键、不影响上一轮数据。
  2. **可清场**：造出来的单号全部登记在案，用例跑完（无论成败）统一清理，测试库不留垃圾。

清理按「先子后父」顺序进行：报工 / 质检 / 追溯流水挂在工单与批次下面，必须先删。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from common.config_loader import Endpoints
from common.db_client import ALLOWED_TABLES, DbClient
from common.http_client import ApiClient

# 默认值集中在此，用例只声明自己关心的字段
DEFAULT_ORDER = {
    "planQty": 100,
    "workshop": "测试车间",
    "remark": "M2 自动化造数",
}


class DataFactory:
    """造数 + 登记 + 清场。"""

    def __init__(
        self,
        api: ApiClient,
        ep: Endpoints,
        db: DbClient,
        prefix: str = "M2",
    ) -> None:
        self.api = api
        self.ep = ep
        self.db = db
        # 形如 M210121252 —— 前缀 + 月日时分，同一天多轮也不会重号
        self.run_id = f"{prefix}{datetime.now():%m%d%H%M}"
        self._seq = 0
        self._orders: set[str] = set()
        self._batches: set[str] = set()
        self._equipment: set[str] = set()
        # 本轮开始时刻，清场时用作兜底时间窗的下界
        self.started_at = datetime.now().replace(microsecond=0)
        # 兜底扫描清掉的行数；>0 说明有用例绕过工厂直接造数，是需要留意的信号
        self.swept = 0

    # ------------------------------------------------------------------ 唯一编码

    def unique(self, kind: str) -> str:
        """生成本轮唯一的编码，kind 决定首位字母（P 产品 / M 物料 / B 批次 / E 设备）。"""
        self._seq += 1
        return f"{kind}{self.run_id}-{self._seq:03d}"

    # ------------------------------------------------------------------ 造数

    def create_order(
        self,
        *,
        plan_qty: int = 100,
        product_name: str = "自动化测试件",
        product_code: str | None = None,
        **extra: Any,
    ) -> dict[str, Any]:
        """创建工单（状态 NEW）。"""
        body = {
            "productCode": product_code or self.unique("P"),
            "productName": product_name,
            "planQty": plan_qty,
            **{k: v for k, v in DEFAULT_ORDER.items() if k != "planQty"},
        }
        body.update(extra)

        res = self.api.post(self.ep.path("work_orders"), json_body=body)
        assert res.ok, f"造数失败：创建工单未成功\n  {res.describe()}"
        order = res.data
        self._orders.add(order["orderNo"])
        return order

    def dispatch_order(self, order_no: str, *, line_code: str = "L-TEST", **extra: Any) -> dict[str, Any]:
        """派工。"""
        body = {"lineCode": line_code, "workshop": "测试车间", **extra}
        res = self.api.put(self.ep.path("work_order_dispatch", orderNo=order_no), json_body=body)
        assert res.ok, f"造数失败：工单派工未成功\n  {res.describe()}"
        return res.data

    def report(self, order_no: str, *, report_qty: int, qualified: int | None = None,
               defective: int | None = None, **extra: Any) -> dict[str, Any]:
        """报工。"""
        body: dict[str, Any] = {"reportQty": report_qty, "worker": f"{self.run_id}-W", **extra}
        if qualified is not None:
            body["qualifiedQty"] = qualified
        if defective is not None:
            body["defectiveQty"] = defective

        res = self.api.post(self.ep.path("work_order_reports", orderNo=order_no), json_body=body)
        assert res.ok, f"造数失败：报工未成功\n  {res.describe()}"
        return res.data

    def create_dispatched_order(self, *, plan_qty: int = 100, **extra: Any) -> dict[str, Any]:
        """创建并派工，返回工单（状态 DISPATCHED）。"""
        order = self.create_order(plan_qty=plan_qty, **extra)
        return self.dispatch_order(order["orderNo"])

    def create_in_progress_order(self, *, plan_qty: int = 100, first_report: int = 10,
                                 **extra: Any) -> dict[str, Any]:
        """创建 → 派工 → 报一次工，返回工单（状态 IN_PROGRESS）。"""
        order = self.create_dispatched_order(plan_qty=plan_qty, **extra)
        return self.report(order["orderNo"], report_qty=first_report, qualified=first_report, defective=0)

    def create_batch(
        self,
        *,
        order_no: str | None = None,
        qty: int = 100,
        material_name: str = "自动化测试原料",
        **extra: Any,
    ) -> dict[str, Any]:
        """创建物料批次。传 order_no 则同时绑定工单。"""
        if order_no:
            batch_no = self.unique("B")
            body = {
                "batchNo": batch_no,
                "materialCode": self.unique("M"),
                "materialName": material_name,
                "orderNo": order_no,
                "qty": qty,
                "unit": "件",
                **extra,
            }
        else:
            batch_no = self.unique("B")
            body = {
                "batchNo": batch_no,
                "materialCode": self.unique("M"),
                "materialName": material_name,
                "qty": qty,
                "unit": "件",
                **extra,
            }

        res = self.api.post(self.ep.path("material_batches"), json_body=body)
        assert res.ok, f"造数失败：创建物料批次未成功\n  {res.describe()}"
        batch = res.data
        self._batches.add(batch["batchNo"])
        return batch

    def equipment_code(self) -> str:
        """生成本轮唯一的设备编号并登记。"""
        code = self.unique("E")
        self._equipment.add(code)
        return code

    # ------------------------------------------------------------------ 清场

    def register_order(self, order_no: str) -> None:
        self._orders.add(order_no)

    def register_batch(self, batch_no: str) -> None:
        self._batches.add(batch_no)

    def register_equipment(self, code: str) -> None:
        self._equipment.add(code)

    def cleanup(self) -> dict[str, int]:
        """清理本轮造出的全部数据。返回各表删除行数，便于确认清场是否生效。

        两层清理：
          ① 精确层 —— 按登记在案的单号删除（快、准，覆盖绝大多数情况）
          ② 兜底层 —— 删除本轮时间窗内仍残留的任何行，捞住「绕过工厂直接调接口造的数据」
        """
        # 安全护栏：只允许动测试库
        self.db.ensure_test_database()

        orders = list(self._orders)
        batches = list(self._batches)
        equipment = list(self._equipment)
        deleted: dict[str, int] = {}

        # ---------------------------------------------- ① 按登记单号精确删除
        # 1) 追溯流水、质检记录同时挂在工单与批次下，先删
        n = self.db.delete_in("mes_trace_record", "order_no", orders)
        n += self.db.delete_in("mes_trace_record", "batch_no", batches)
        deleted["mes_trace_record"] = n

        n = self.db.delete_in("mes_quality_inspection", "order_no", orders)
        n += self.db.delete_in("mes_quality_inspection", "batch_no", batches)
        deleted["mes_quality_inspection"] = n

        # 2) 报工挂在工单下
        deleted["mes_work_report"] = self.db.delete_in("mes_work_report", "order_no", orders)

        # 3) 批次
        n = self.db.delete_in("mes_material_batch", "batch_no", batches)
        n += self.db.delete_in("mes_material_batch", "order_no", orders)
        deleted["mes_material_batch"] = n

        # 4) 工单
        deleted["mes_work_order"] = self.db.delete_in("mes_work_order", "order_no", orders)

        # 5) 数采数据靠设备编号识别
        deleted["mes_device_data"] = self.db.delete_in("mes_device_data", "equipment_code", equipment)

        # ---------------------------------------------- ② 时间窗兜底扫描
        # 单机顺序执行，不存在并发跑多轮的情况，因此时间窗是安全的兜底口径。
        for table in sorted(ALLOWED_TABLES):
            extra = self.db.delete_since(table, self.started_at)
            if extra:
                deleted[table] = deleted.get(table, 0) + extra
                self.swept += extra

        self._orders.clear()
        self._batches.clear()
        self._equipment.clear()
        return deleted

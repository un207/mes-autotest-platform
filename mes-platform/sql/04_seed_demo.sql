-- =============================================================
--  迷你 MES 系统 · 04 演示数据（可选）
--  仅用于本地起服务后手动点 Swagger 自测，不进 CI 流程。
--  数据本身不代表任何真实业务，全部为构造值。
--  执行方式：
--    "C:\Program Files\MySQL\MySQL Server 5.7\bin\mysql.exe" -uroot -p mes < 04_seed_demo.sql
-- =============================================================

USE `mes`;

SET NAMES utf8mb4;

-- 工单：一条已派工待报工，一条在产
INSERT INTO `mes_work_order` (`order_no`, `product_code`, `product_name`, `plan_qty`, `finished_qty`, `qualified_qty`,
                              `defective_qty`, `status`, `line_code`, `workshop`, `plan_start_time`, `plan_end_time`,
                              `remark`)
VALUES ('WO-DEMO-0001', 'P-1001', '法兰盘 A 型', 500, 0, 0, 0, 'NEW', NULL, NULL, NULL, NULL, '演示数据'),
       ('WO-DEMO-0002', 'P-1002', '齿轮箱壳体', 300, 120, 116, 4, 'IN_PROGRESS', 'L01', '一号车间',
        DATE_SUB(NOW(), INTERVAL 1 DAY), DATE_ADD(NOW(), INTERVAL 1 DAY), '演示数据');

-- 报工：对应 WO-DEMO-0002
INSERT INTO `mes_work_report` (`report_no`, `order_no`, `report_qty`, `qualified_qty`, `defective_qty`, `worker`,
                               `equipment_code`, `report_time`, `remark`)
VALUES ('WR-DEMO-0001', 'WO-DEMO-0002', 120, 116, 4, '徐伟杰', 'EQ-001', NOW(), '演示数据');

-- 物料批次：绑定在产工单
INSERT INTO `mes_material_batch` (`batch_no`, `material_code`, `material_name`, `order_no`, `supplier`, `qty`, `unit`,
                                  `inbound_time`, `status`, `remark`)
VALUES ('MB-DEMO-0001', 'M-2001', '铸铁毛坯', 'WO-DEMO-0002', '本地铸造厂', 300, '件', NOW(), 'IN_USE', '演示数据');

-- 追溯流水：入库 + 投产
INSERT INTO `mes_trace_record` (`trace_no`, `batch_no`, `order_no`, `node_type`, `node_desc`, `operator`, `trace_time`)
VALUES ('TR-DEMO-0001', 'MB-DEMO-0001', 'WO-DEMO-0002', 'INBOUND', '来料入库 300件，绑定工单 WO-DEMO-0002', '本地铸造厂', NOW()),
       ('TR-DEMO-0002', 'MB-DEMO-0001', 'WO-DEMO-0002', 'PRODUCE', '投产报工 120 件', '徐伟杰', NOW());

-- 质检：一条合格、一条不合格（含不良代码）
INSERT INTO `mes_quality_inspection` (`inspect_no`, `order_no`, `batch_no`, `inspect_type`, `inspect_qty`,
                                      `qualified_qty`, `defective_qty`, `defect_code`, `result`, `inspector`,
                                      `inspect_time`, `remark`)
VALUES ('QI-DEMO-0001', 'WO-DEMO-0002', 'MB-DEMO-0001', 'IQC', 50, 50, 0, NULL, 'PASS', '质检员A', NOW(), '演示数据'),
       ('QI-DEMO-0002', 'WO-DEMO-0002', 'MB-DEMO-0001', 'IPQC', 10, 8, 2, 'D-尺寸超差', 'FAIL', '质检员A', NOW(),
        '演示数据');

-- 设备数采：1 条正常 + 1 条超限（可疑）+ 1 条脏数据（异常）
INSERT INTO `mes_device_data` (`equipment_code`, `line_code`, `metric`, `metric_value`, `raw_value`, `unit`,
                               `quality_flag`, `quality_message`, `collect_time`)
VALUES ('EQ-001', 'L01', 'OUTPUT', 120.0000, '120', '件', 'OK', NULL, NOW()),
       ('EQ-001', 'L01', 'TEMPERATURE', 512.0000, '512', '℃', 'SUSPECT', '数值超出合理区间 [-50, 200]', NOW()),
       ('EQ-002', 'L01', 'STATUS', NULL, '###', NULL, 'BAD', '上报值无法解析为数值，已标记异常且不入账', NOW());

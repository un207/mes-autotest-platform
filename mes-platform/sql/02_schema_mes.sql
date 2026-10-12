-- =============================================================
--  迷你 MES 系统 · 02 业务库表结构（mes）
--  MySQL 5.7 / utf8mb4 / InnoDB
--  设计约定：
--    1) 所有表统一带 create_time / update_time / deleted（逻辑删除），
--       应用层由 MetaObjectHandler 自动填充，物理删除一律不做。
--    2) 枚举字段以 VARCHAR 存枚举 name()，便于脚本直接断言字面量，
--       也让数据库里存的值可读、可被 DBA 直接审。
--    3) 唯一键只加在业务单号上；idx_* 为查询索引，按最左前缀组织。
--  执行方式：
--    "C:\Program Files\MySQL\MySQL Server 5.7\bin\mysql.exe" -uroot -p mes < 02_schema_mes.sql
-- =============================================================

USE `mes`;

SET NAMES utf8mb4;

-- -------------------------------------------------------------
-- 1. 生产工单
-- -------------------------------------------------------------
DROP TABLE IF EXISTS `mes_work_order`;
CREATE TABLE `mes_work_order`
(
    `id`                BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
    `order_no`          VARCHAR(32)  NOT NULL COMMENT '工单号',
    `product_code`      VARCHAR(32)  NOT NULL COMMENT '产品编码',
    `product_name`      VARCHAR(64)  NOT NULL COMMENT '产品名称',
    `plan_qty`          INT          NOT NULL COMMENT '计划数量',
    `finished_qty`      INT          NOT NULL DEFAULT 0 COMMENT '累计报工数量',
    `qualified_qty`     INT          NOT NULL DEFAULT 0 COMMENT '累计合格数量',
    `defective_qty`     INT          NOT NULL DEFAULT 0 COMMENT '累计不良数量',
    `status`            VARCHAR(16)  NOT NULL DEFAULT 'NEW' COMMENT '状态：NEW/DISPATCHED/IN_PROGRESS/CLOSED',
    `line_code`         VARCHAR(32)           DEFAULT NULL COMMENT '产线编号',
    `workshop`          VARCHAR(64)           DEFAULT NULL COMMENT '车间',
    `plan_start_time`   DATETIME              DEFAULT NULL COMMENT '计划开工时间',
    `plan_end_time`     DATETIME              DEFAULT NULL COMMENT '计划完工时间',
    `actual_start_time` DATETIME              DEFAULT NULL COMMENT '实际开工时间（首次报工时刻）',
    `actual_end_time`   DATETIME              DEFAULT NULL COMMENT '实际完工时间（关闭时刻）',
    `remark`            VARCHAR(255)          DEFAULT NULL COMMENT '备注',
    `create_time`       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `update_time`       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    `deleted`           TINYINT      NOT NULL DEFAULT 0 COMMENT '逻辑删除：0未删 1已删',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_order_no` (`order_no`),
    KEY `idx_status` (`status`),
    KEY `idx_line_code` (`line_code`),
    KEY `idx_create_time` (`create_time`)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4 COMMENT ='生产工单';

-- -------------------------------------------------------------
-- 2. 报工记录
-- -------------------------------------------------------------
DROP TABLE IF EXISTS `mes_work_report`;
CREATE TABLE `mes_work_report`
(
    `id`             BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
    `report_no`      VARCHAR(32)  NOT NULL COMMENT '报工单号',
    `order_no`       VARCHAR(32)  NOT NULL COMMENT '工单号',
    `report_qty`     INT          NOT NULL COMMENT '本次报工数量',
    `qualified_qty`  INT          NOT NULL COMMENT '本次合格数量',
    `defective_qty`  INT          NOT NULL COMMENT '本次不良数量',
    `worker`         VARCHAR(32)  NOT NULL COMMENT '报工人',
    `equipment_code` VARCHAR(32)           DEFAULT NULL COMMENT '报工设备编号',
    `report_time`    DATETIME     NOT NULL COMMENT '报工时间',
    `remark`         VARCHAR(255)          DEFAULT NULL COMMENT '备注',
    `create_time`    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `update_time`    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    `deleted`        TINYINT      NOT NULL DEFAULT 0 COMMENT '逻辑删除：0未删 1已删',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_report_no` (`report_no`),
    KEY `idx_order_no` (`order_no`),
    KEY `idx_report_time` (`report_time`)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4 COMMENT ='报工记录';

-- -------------------------------------------------------------
-- 3. 质检记录
-- -------------------------------------------------------------
DROP TABLE IF EXISTS `mes_quality_inspection`;
CREATE TABLE `mes_quality_inspection`
(
    `id`            BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
    `inspect_no`    VARCHAR(32)  NOT NULL COMMENT '质检单号',
    `order_no`      VARCHAR(32)  NOT NULL COMMENT '工单号',
    `batch_no`      VARCHAR(32)           DEFAULT NULL COMMENT '物料批次号',
    `inspect_type`  VARCHAR(16)  NOT NULL COMMENT '质检类型：IQC/IPQC/FQC/OQC',
    `inspect_qty`   INT          NOT NULL COMMENT '检验数量',
    `qualified_qty` INT          NOT NULL COMMENT '合格数量',
    `defective_qty` INT          NOT NULL COMMENT '不良数量',
    `defect_code`   VARCHAR(32)           DEFAULT NULL COMMENT '不良代码，不良数>0 时必填',
    `result`        VARCHAR(16)  NOT NULL COMMENT '结论：PASS/FAIL',
    `inspector`     VARCHAR(32)  NOT NULL COMMENT '质检员',
    `inspect_time`  DATETIME     NOT NULL COMMENT '检验时间',
    `remark`        VARCHAR(255)          DEFAULT NULL COMMENT '备注',
    `create_time`   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `update_time`   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    `deleted`       TINYINT      NOT NULL DEFAULT 0 COMMENT '逻辑删除：0未删 1已删',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_inspect_no` (`inspect_no`),
    KEY `idx_order_no` (`order_no`),
    KEY `idx_batch_no` (`batch_no`),
    KEY `idx_result` (`result`),
    KEY `idx_defect_code` (`defect_code`)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4 COMMENT ='质检记录';

-- -------------------------------------------------------------
-- 4. 物料批次
-- -------------------------------------------------------------
DROP TABLE IF EXISTS `mes_material_batch`;
CREATE TABLE `mes_material_batch`
(
    `id`            BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
    `batch_no`      VARCHAR(32)  NOT NULL COMMENT '批次号',
    `material_code` VARCHAR(32)  NOT NULL COMMENT '物料编码',
    `material_name` VARCHAR(64)  NOT NULL COMMENT '物料名称',
    `order_no`      VARCHAR(32)           DEFAULT NULL COMMENT '绑定工单号，未领用时为空',
    `supplier`      VARCHAR(64)           DEFAULT NULL COMMENT '供应商',
    `qty`           INT          NOT NULL COMMENT '数量',
    `unit`          VARCHAR(16)           DEFAULT NULL COMMENT '单位',
    `inbound_time`  DATETIME     NOT NULL COMMENT '入库时间',
    `status`        VARCHAR(16)  NOT NULL COMMENT '状态：IN_STOCK/IN_USE/CONSUMED/FROZEN',
    `remark`        VARCHAR(255)          DEFAULT NULL COMMENT '备注',
    `create_time`   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `update_time`   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    `deleted`       TINYINT      NOT NULL DEFAULT 0 COMMENT '逻辑删除：0未删 1已删',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_batch_no` (`batch_no`),
    KEY `idx_order_no` (`order_no`),
    KEY `idx_material_code` (`material_code`),
    KEY `idx_status` (`status`)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4 COMMENT ='物料批次';

-- -------------------------------------------------------------
-- 5. 追溯流水（只增不改）
-- -------------------------------------------------------------
DROP TABLE IF EXISTS `mes_trace_record`;
CREATE TABLE `mes_trace_record`
(
    `id`          BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
    `trace_no`    VARCHAR(32)  NOT NULL COMMENT '追溯单号',
    `batch_no`    VARCHAR(32)           DEFAULT NULL COMMENT '物料批次号',
    `order_no`    VARCHAR(32)           DEFAULT NULL COMMENT '工单号',
    `node_type`   VARCHAR(16)  NOT NULL COMMENT '节点类型：INBOUND/PRODUCE/INSPECT/OUTBOUND',
    `node_desc`   VARCHAR(255)          DEFAULT NULL COMMENT '节点描述',
    `operator`    VARCHAR(32)           DEFAULT NULL COMMENT '操作人/来源',
    `trace_time`  DATETIME     NOT NULL COMMENT '节点发生时间',
    `create_time` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `update_time` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    `deleted`     TINYINT      NOT NULL DEFAULT 0 COMMENT '逻辑删除：0未删 1已删',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_trace_no` (`trace_no`),
    KEY `idx_batch_no` (`batch_no`),
    KEY `idx_order_no` (`order_no`),
    KEY `idx_node_type` (`node_type`)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4 COMMENT ='追溯流水';

-- -------------------------------------------------------------
-- 6. 设备数采记录
-- -------------------------------------------------------------
DROP TABLE IF EXISTS `mes_device_data`;
CREATE TABLE `mes_device_data`
(
    `id`              BIGINT        NOT NULL AUTO_INCREMENT COMMENT '主键',
    `equipment_code`  VARCHAR(32)   NOT NULL COMMENT '设备编号',
    `line_code`       VARCHAR(32)            DEFAULT NULL COMMENT '产线编号',
    `metric`          VARCHAR(16)   NOT NULL COMMENT '指标：OUTPUT/STATUS/TEMPERATURE',
    `metric_value`    DECIMAL(18, 4)         DEFAULT NULL COMMENT '解析后数值，解析失败为空',
    `raw_value`       VARCHAR(64)   NOT NULL COMMENT '原始上报值',
    `unit`            VARCHAR(16)            DEFAULT NULL COMMENT '单位',
    `quality_flag`    VARCHAR(16)   NOT NULL COMMENT '数据质量：OK/SUSPECT/BAD',
    `quality_message` VARCHAR(255)           DEFAULT NULL COMMENT '异常原因',
    `collect_time`    DATETIME      NOT NULL COMMENT '采集时间',
    `create_time`     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `update_time`     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    `deleted`         TINYINT       NOT NULL DEFAULT 0 COMMENT '逻辑删除：0未删 1已删',
    PRIMARY KEY (`id`),
    KEY `idx_equipment_time` (`equipment_code`, `collect_time`),
    KEY `idx_quality_flag` (`quality_flag`),
    KEY `idx_metric` (`metric`)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4 COMMENT ='设备数采记录';

-- 校验：应输出 6 张表
SHOW TABLES;

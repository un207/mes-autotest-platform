-- =============================================================
--  迷你 MES 系统 · 03 测试库表结构（mes_test）
--  与 mes 结构完全一致，用 CREATE TABLE ... LIKE 复制，避免两份 DDL 漂移。
--  执行前须先跑 02_schema_mes.sql（依赖 mes 库中已存在同名表）。
--  用途：M2 pytest 造数与「接口返回 + 落库」双重断言，用例前后清数互不污染。
--  执行方式：
--    "C:\Program Files\MySQL\MySQL Server 5.7\bin\mysql.exe" -uroot -p < 03_schema_mes_test.sql
-- =============================================================

DROP DATABASE IF EXISTS `mes_test`;
CREATE DATABASE `mes_test`
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_general_ci;

CREATE TABLE `mes_test`.`mes_work_order` LIKE `mes`.`mes_work_order`;
CREATE TABLE `mes_test`.`mes_work_report` LIKE `mes`.`mes_work_report`;
CREATE TABLE `mes_test`.`mes_quality_inspection` LIKE `mes`.`mes_quality_inspection`;
CREATE TABLE `mes_test`.`mes_material_batch` LIKE `mes`.`mes_material_batch`;
CREATE TABLE `mes_test`.`mes_trace_record` LIKE `mes`.`mes_trace_record`;
CREATE TABLE `mes_test`.`mes_device_data` LIKE `mes`.`mes_device_data`;

-- 校验：应输出 6 张表，且与 mes 结构一致
SHOW TABLES FROM `mes_test`;

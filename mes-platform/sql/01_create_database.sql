-- =============================================================
--  迷你 MES 系统 · 01 建库脚本
--  目标实例：MySQL 5.7（本机 C:\Program Files\MySQL\MySQL Server 5.7）
--  两个 Schema：mes（业务库） / mes_test（测试库，M2 pytest 造数与落库校验用）
--  字符集：utf8mb4，排序规则 utf8mb4_general_ci（5.7 下索引长度更友好）
--  执行方式：
--    "C:\Program Files\MySQL\MySQL Server 5.7\bin\mysql.exe" -uroot -p < 01_create_database.sql
-- =============================================================

CREATE DATABASE IF NOT EXISTS `mes`
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_general_ci;

CREATE DATABASE IF NOT EXISTS `mes_test`
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_general_ci;

-- 校验
SHOW DATABASES LIKE 'mes%';

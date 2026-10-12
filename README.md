# MES 自动化测试平台

[![MES 接口自动化测试](https://github.com/un207/mes-autotest-platform/actions/workflows/api-test.yml/badge.svg)](https://github.com/un207/mes-autotest-platform/actions/workflows/api-test.yml)

一个面向 **MES（制造执行系统）** 场景的完整实践项目。由四部分组成，职责分离：

| 目录 | 角色 | 说明 |
|------|------|------|
| [`mes-platform/`](./mes-platform) | **被测对象** | 迷你 MES 后端：工单 / 报工 / 质检 / 物料追溯 / 设备数采。Spring Boot 3.2 + MyBatis-Plus + MySQL |
| [`mes-autotest/`](./mes-autotest) | **测试框架** | 接口自动化：pytest + requests + PyMySQL，**99 条用例**，含「接口返回 + 落库」双重断言 |
| [`mes-simulator/`](./mes-simulator) | **设备模拟器** | Modbus TCP 模拟产线设备，把数据送进 MES，并注入 6 种异常验证质量把关 |
| [`mes-console/`](./mes-console) | **管理界面** | Vue 3 + Element Plus，把 24 个接口变成可操作的可视化界面 |

> 为什么不合成一个工程：业务系统与测试框架混在一起就变成「自己测自己」，测试的独立性不成立。
> 四部分各自是一份完整、可独立讲述的东西。

---

## 这个项目解决什么问题

真实工厂里，一张生产订单要这样走：**下单 → 派工 → 报工 → 质检 → 追溯 → 关闭**。
MES 就是管这条链路的系统，同时还得接住设备上报的产量与温度数据。
这条链路有个特点：**数据一旦错了，事后极难查**。比如「报工 100 件、合格 60 件」这种不守恒的记录，
会让良率统计与成本核算全部失真；原料批次如果没绑对工单，出了质量问题就追不回是哪批料。

所以本项目做了四件事：

1. **把业务规则用代码焊死**（`mes-platform`）—— 数量不守恒、非法状态流转、脏数据，一律当场拒绝
2. **用自动化用例把每条规则都钉住**（`mes-autotest`）—— 任何人改动代码导致规则失效，CI 立刻红
3. **造出真实的工业数据来喂它**（`mes-simulator`）—— 并主动注入故障，验证把关真的有效而不是形同虚设
4. **给出可视化的操作界面**（`mes-console`）—— 让人能直接看到系统在运行、数据在流动

---

## 技术栈

| 层 | 选型 |
|----|------|
| 被测系统 | Java 17 · Spring Boot 3.2.12 · MyBatis-Plus 3.5.9 · MySQL 5.7 |
| 测试框架 | Python 3.13 · pytest 9.1 · requests · PyMySQL · PyYAML（数据驱动）· Allure |
| 设备模拟 | Python 3.13 · pymodbus 3.16（Modbus TCP） |
| 管理界面 | Vue 3.5 · Element Plus 2.9 · ECharts 5 · Vite 6 |
| 持续集成 | GitHub Actions（MySQL 5.7 容器 + 全量回归 + 设备模拟验证 + 报告归档） |

---

## 测试规模与覆盖

| 模块 | 用例数 | 覆盖重点 |
|------|--------|----------|
| 服务自检 | 3 | 存活/就绪、接口与直连的库版本交叉校验 |
| 工单主链路 | 1 | 建单→派工→批次→报工→质检→双向追溯→关闭，每步含落库断言 |
| 工单业务规则 | 36 | 数量守恒、超报拦截、状态机、参数校验、分页边界 |
| 质量检验规则 | 19 | 结论推导、不良代码必填、批次关联一致性 |
| 物料批次与追溯 | 10 | 批次状态流转、防改绑串线、双向追溯、节点顺序 |
| 设备数采质量 | 24 | 三层把关（可解析性/工况区间/时间合理性）、批量边界 |
| 统计报表 | 6 | 总览口径反算、日报区间筛选、低良率排行 |
| **合计** | **99** | 冒烟 10 · 回归 89 · 需落库校验 60 |

### 三条测试设计上的硬要求

**① 不只测接口，还要测落库。** 接口返回 200 不代表数据真的写进库了。
关键用例都多做一步直连 `mes_test` 校验：接口说报工 120 件，库里 `finished_qty` 就必须是 120，
且报工记录恰好 1 条、追溯节点也确实落了。

**② 数据可重复、自动清场。** 每轮用例生成的编码都带唯一前缀，反复跑不撞唯一键；
跑完自动清理（两层机制：按登记单号精确删 + 按时间窗兜底扫），测试库不留垃圾。
框架还会前置校验「配置的库名以 `_test` 结尾」且「接口写入的库与校验的库是同一个」，环境不对直接拒绝执行。

**③ 主动注入故障，验证把关有效。** 只发正常数据的话，MES 的三层质量把关从未被走通过。
设备模拟器提供 6 种真实故障形态（过热、状态码非法、传感器故障、乱码上报、产量超上限、时钟漂移），
逐个验证 MES 是否真能识别、原因是否指向正确。

---

## 快速开始

```bash
# 1) 建库（需要本地 MySQL 5.7）
cd mes-platform/sql
mysql -uroot -p < 01_create_database.sql     # 建 mes / mes_test
mysql -uroot -p mes < 02_schema_mes.sql
mysql -uroot -p < 03_schema_mes_test.sql

# 2) 启动被测系统（另开终端）
cd ../mes-platform
mvn spring-boot:run

# 3) 跑自动化用例（另开终端）
cd ../mes-autotest
pip install -r requirements.txt
pytest                        # 99 条用例
python tools/run.py --scope smoke   # 一键：跑用例 + 出三种报告

# 4) 起设备模拟器，造真实工业数据
cd ../mes-simulator
pip install -r requirements.txt
python run.py --fault temp_overheat   # 带一个异常上报
python verify.py                     # 端到端验证质量把关

# 5) 起管理界面
cd ../mes-console
npm install
npm run dev                   # http://localhost:5173
```

---

## 持续集成

`.github/workflows/api-test.yml`：

```
MySQL 5.7 容器 → 建库 → 构建被测系统 → test profile 启动 → 轮询就绪
  → 99 条接口用例（含落库断言）
  → 设备模拟器自检（Modbus 通路 + 设备逻辑 + 异常注入）
  → 设备模拟器端到端验证（模拟器 → MES 数采 → 质量判定）
  → 生成三种报告 → 归档
```

- **push / PR**：限定路径触发（只改文档不跑，不烧 runner 额度）
- **手动触发**：可选全量或只跑冒烟
- **定时**：每天北京时间 06:00 全量回归，用于发现环境漂移导致的慢性问题

被测系统一律以 `test` profile 启动，数据写入 `mes_test`，与业务库 `mes` 物理隔离。

---

## 交付进度

| 阶段 | 内容 | 状态 |
|------|------|------|
| M1 | 迷你 MES 后端（6 张表 / 24 个接口） | 完成 |
| M2 | pytest 框架 + 99 条用例 + 落库双重断言 | 完成 |
| M3 | GitHub Actions 回归 + Allure 报告 + 通过率趋势 | 完成 |
| M4 | 设备模拟器（Modbus TCP）+ Vue 管理界面 | 完成 |
| M5 | 性能压测 / 消息队列（可选） | 计划中 |

---

## 已知边界

如实说明，不夸大：

- 单机学习级项目，**未做高并发设计**。并发正确性靠工单行锁（`SELECT … FOR UPDATE`）保证，未用分布式锁
- **未接入真实产线设备**，设备侧数据由 Modbus 模拟器产生
- 设备模拟器只实现了功能码 3（读保持寄存器），只起单台设备
- 登录认证与角色权限尚未实现，接口与管理界面均开放访问
- 用例按顺序执行设计，**不支持并发跑多轮**（清场的时间窗兜底基于此假设）

---

## 工程文档

- [`mes-platform/README.md`](./mes-platform/README.md) —— 被测系统的接口契约、业务规则、建表说明
- [`mes-autotest/README.md`](./mes-autotest/README.md) —— 测试框架的目录结构、设计取舍、怎么加用例
- [`mes-simulator/README.md`](./mes-simulator/README.md) —— Modbus 点表、异常场景、OT/IT 链路说明
- [`mes-console/README.md`](./mes-console/README.md) —— 管理界面的页面构成与设计选择

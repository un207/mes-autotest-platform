# 迷你 MES 系统（mes-platform）

> MES 场景自动化测试平台项目的 **M1 交付物**：被测对象的后端服务。
> 技术栈：Spring Boot 3.2.12 + JDK 17 + MyBatis-Plus 3.5.9 + MySQL 5.7。

本仓库是「被测系统」，与「测试平台」严格分离。M2 阶段的 pytest 脚本库将独立成工程，通过 HTTP 调用本服务的接口，
并直连 `mes_test` 库做「接口返回 + 落库」双重断言。

---

## 1. 快速开始

### 1.1 前置条件

| 项 | 要求 | 本机位置 |
|----|------|----------|
| JDK | 17 | `C:\Users\Administrator\.jdks\temurin-17.0.20.1` |
| Maven | 3.9+（IDEA 内置即可） | `D:\Program Files\JetBrains\IntelliJ IDEA 2026.1.4\plugins\maven\lib\maven3` |
| MySQL | 5.7 | `C:\Program Files\MySQL\MySQL Server 5.7` |

### 1.2 初始化数据库

```bash
cd sql
"C:\Program Files\MySQL\MySQL Server 5.7\bin\mysql.exe" -uroot -p < 01_create_database.sql   # 建 mes / mes_test
"C:\Program Files\MySQL\MySQL Server 5.7\bin\mysql.exe" -uroot -p mes < 02_schema_mes.sql    # mes 建表
"C:\Program Files\MySQL\MySQL Server 5.7\bin\mysql.exe" -uroot -p < 03_schema_mes_test.sql   # mes_test 建表
"C:\Program Files\MySQL\MySQL Server 5.7\bin\mysql.exe" -uroot -p mes < 04_seed_demo.sql     # 可选：演示数据
```

### 1.3 配置数据库口令

口令**不写进仓库**，一律走环境变量（未设置时回落到本地默认值 `root/123456`）：

```bash
set MES_DB_USER=root
set MES_DB_PASSWORD=你的口令
```

### 1.4 启动与自检

```bash
mvn spring-boot:run
# 或 IDEA 中直接运行 MesPlatformApplication

# 自检
curl http://localhost:8080/api/health     # 进程存活
curl http://localhost:8080/api/ready      # 就绪（含 MySQL 连通性，不通返回 503）
```

接口文档（Swagger UI）：<http://localhost:8080/swagger-ui.html>
OpenAPI JSON（M2 脚本核对契约用）：<http://localhost:8080/v3/api-docs>

> **环境陷阱（仅 WorkBuddy 沙箱终端）**：沙箱会注入 `SERVER__PORT` 变量，被 Spring Boot 的宽松绑定
> 识别成 `server.port`，导致服务实际监听在沙箱代理端口上而非 8080。在沙箱内启动前先清掉：
> `unset SERVER__PORT SERVER__HOST`。本机 IDEA / CMD / PowerShell 里不存在该变量，无需处理。

### 1.5 跑单测（不依赖数据库）

```bash
mvn test
```

### 1.6 在 IntelliJ IDEA 里运行

工程已预置 `.idea/misc.xml`、`.idea/encodings.xml`、`.idea/compiler.xml`，把项目 SDK 锁定为 JDK 17
并开启 Lombok 注解处理（这三个文件被 `.gitignore` 忽略，不会进仓库）。

1. `File` → `Open`，选择目录 `D:\Program Files\WorkBuddy-workspace3\mes-platform`（`pom.xml` 所在这一层）。
2. 弹出 **Trust Project** 时点信任（该路径此前未被加入 IDEA 受信任列表）。
3. 若右下角提示 Maven 项目待导入，点 **Load Maven Project**。依赖已全部在本地仓库，导入很快，无需等待联网下载。
4. 核对 SDK：`File` → `Project Structure` → `Project`，SDK 应为 **temurin-17**、Language level 为 **17**。
   若显示 `1.8`，手动改成 `temurin-17`（本机已注册该 SDK）—— 选错 JDK 是 Spring Boot 3 起不来最常见的原因。
5. 打开 `src/main/java/com/xwj/mes/MesPlatformApplication.java`，点 `main` 左侧绿色三角 → **Run**。
6. 控制台出现 `Started MesPlatformApplication` 即成功，Tomcat 监听 **8080**。

> IDEA 里**不需要** 1.4 节那条 `unset SERVER__PORT` —— 那是 WorkBuddy 沙箱终端特有的环境变量污染，IDEA 中不存在。

**跑起来后看什么**

| 入口 | 用途 |
|------|------|
| <http://localhost:8080/swagger-ui.html> | 接口文档，可点 `Try it out` 直接发真实请求 |
| <http://localhost:8080/api/ready> | 就绪自检，含 MySQL 连通性 |
| <http://localhost:8080/api/stats/overview> | 平台总览指标，一条请求看到跨表聚合结果 |

库中已有演示数据（`sql/04_seed_demo.sql`），启动后即可查到工单、质检、批次、数采记录，不会是空列表。

**编辑器报「找不到 getXxx()」但 Maven 能编译**：说明 Lombok 注解处理被关了 ——
`File` → `Settings` → `Build, Execution, Deployment` → `Compiler` → `Annotation Processors`，
勾选 **Enable annotation processing**。

---

## 2. 接口契约

### 2.1 统一响应体

**任何** 已路由到 Controller 的请求都返回 HTTP 200，业务结果由 `code` 承载，测试脚本只需一套断言模板：

```json
{
  "code": 0,
  "message": "成功",
  "data": { },
  "traceId": "a1b2c3d4e5f6a7b8",
  "timestamp": 1760700000000
}
```

| HTTP | 含义 | 何时出现 |
|------|------|----------|
| 200 | 请求已到达业务层 | 成功、参数校验失败、业务规则拒绝、业务上资源不存在 |
| 404 | 路由/静态资源不存在 | 请求压根没匹配上任何接口 |
| 500 | 未预期异常 | 代码缺陷，凭 `traceId` 查日志 |

`traceId` 同时写入响应头 `X-Request-Id`；若调用方自带该请求头则原样沿用，便于脚本串联一次执行产生的多条请求日志。

### 2.2 业务状态码

| code | 含义 |
|------|------|
| 0 | 成功 |
| 40000 / 40001 | 参数校验失败 / 请求体格式错误 |
| 40400 | 资源不存在（业务语义） |
| 40900 / 40901 | 业务状态冲突 / 数据已存在 |
| 50000 / 50001 | 系统内部错误 / 数据库访问异常 |
| 50300 | 服务依赖不可用 |

### 2.3 接口清单

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health`、`/api/ready` | 存活 / 就绪自检 |
| POST | `/api/work-orders` | 创建工单 |
| GET | `/api/work-orders` | 分页查询（status / lineCode / productCode / keyword） |
| GET | `/api/work-orders/{orderNo}` | 工单详情（含报工明细） |
| GET | `/api/work-orders/{orderNo}/reports` | 报工记录 |
| PUT | `/api/work-orders/{orderNo}/dispatch` | 派工 |
| POST | `/api/work-orders/{orderNo}/reports` | 报工 |
| PUT | `/api/work-orders/{orderNo}/close` | 关闭工单 |
| POST | `/api/quality-inspections` | 录入质检 |
| GET | `/api/quality-inspections` | 分页查询质检 |
| GET | `/api/quality-inspections/defects/{orderNo}` | 按工单追溯不良明细 |
| GET | `/api/quality-inspections/defect-summary` | 不良代码分布 |
| POST | `/api/material-batches` | 物料批次建档 |
| GET | `/api/material-batches` | 分页查询批次 |
| PUT | `/api/material-batches/{batchNo}/bind?orderNo=` | 批次绑定工单 |
| PUT | `/api/material-batches/{batchNo}/outbound` | 批次出货消耗 |
| GET | `/api/traces/batch/{batchNo}` | 正向追溯（批次 → 工单 → 节点流水） |
| GET | `/api/traces/order/{orderNo}` | 反向追溯（工单 → 批次 + 节点 + 不良明细） |
| POST | `/api/device-data`、`/api/device-data/batch` | 设备数采上报（单条 / 批量≤200） |
| GET | `/api/device-data`、`/api/device-data/abnormal` | 数采查询 / 异常数据 |
| GET | `/api/stats/overview` | 平台总览指标 |
| GET | `/api/stats/production?from=&to=&lineCode=` | 产量日报（按日期 × 产线） |
| GET | `/api/stats/yield/orders?limit=` | 低良率工单排行 |

---

## 3. 核心业务规则（M2 用例设计蓝本）

**工单状态机**

```
NEW ──派工──▶ DISPATCHED ──首次报工──▶ IN_PROGRESS ──关闭──▶ CLOSED
                   │                        │
                   └────────关闭────────────┘
```

- 只有 `DISPATCHED` / `IN_PROGRESS` 可报工；`NEW` 与 `CLOSED` 一律 40900。
- `NEW` 不允许关闭，`CLOSED` 不可重复关闭。

**数量守恒**：合格数 + 不良数 **必须等于** 报工数（质检同理）。两者都不传时按「全合格」处理；只传其一则自动推算。
累计报工数超过计划数时直接拦截（40900），不放过超报。

**质检结论**：由数量推导，不允许人工背离 —— 不良数 > 0 即 `FAIL`；存在不良时 `defectCode` 必填，
否则追溯链在不良环节断裂。

**批次绑定**：一个批次只允许绑定一个工单，改绑直接 40900，防止追溯串线；`CONSUMED` 批次不可再绑定或重复出货。

**数采数据质量**（M4 模拟器异常注入的落点）：

| 层级 | 判定 | 结果 |
|------|------|------|
| 可解析性 | `rawValue` 无法转数值 | `BAD`，数值不入账但留原始串 |
| 工况区间 | 温度 ∉ [-50, 200]℃ / 产量 ∉ [0, 1000000] / 状态 ∉ [0, 10] | `SUSPECT`，数值仍留档 |
| 时间合理性 | 采集时间晚于当前 5 分钟以上 | `SUSPECT`，疑设备时钟异常 |

脏数据**一律留痕**，不做静默丢弃 —— 现场最怕「脏数据静默入账」。

---

## 4. 工程结构

```
src/main/java/com/xwj/mes/
├── MesPlatformApplication.java
├── common/                      # 跨模块基础设施
│   ├── api/                     # ApiResponse / PageResult / PageQuery / ErrorCode
│   ├── exception/               # BizException + GlobalExceptionHandler
│   ├── entity/BaseEntity.java   # 主键 + 审计时间 + 逻辑删除
│   ├── config/                  # MyBatis-Plus 插件 / 审计填充 / CORS / OpenAPI / traceId 过滤器
│   ├── health/                  # /api/health、/api/ready
│   └── util/                    # 单据号生成、文本清洗
├── workorder/                   # 工单 + 报工（状态机、数量守恒）
├── quality/                     # 质检（结论推导、不良追溯）
├── material/                    # 物料批次 + 追溯流水（正/反向追溯）
├── device/                      # 设备数采（脏数据质量判定）
└── stats/                       # 统计报表（聚合全部下沉 SQL）

sql/                              # 01 建库 → 02 mes 建表 → 03 mes_test 建表 → 04 演示数据
```

按**业务域**分包而非按技术层分包：新增「设备管理」等模块时只需加一个包，不动框架代码。

---

## 5. 当前进度与后续

| 里程碑 | 状态 | 说明 |
|--------|------|------|
| **M1 迷你 MES 后端** | ✅ 骨架完成 | 6 张表、24 个接口地址（29 个操作）、状态机与守恒规则落地、单测覆盖核心规则 |
| M2 pytest 框架 | 待开始 | requests 封装 + YAML 数据驱动 + SQL 落库校验（连 `mes_test`） |
| M3 CI + 报告 | 待开始 | GitHub Actions 自动回归 + Allure 报告 |
| M4 设备模拟 + 平台界面 | 待开始 | pymodbus 从站 + Vue 管理界面 |
| M5 性能 / MQ（可选） | 待开始 | Locust 压测 / RabbitMQ |

**已知边界**（面试如实说明，不夸大）：
- 单机学习级项目，未做高并发设计；并发正确性靠工单行锁（`FOR UPDATE`）保证，未做分布式锁。
- 未接入真实 PLC/产线，设备侧由 M4 的 Modbus 模拟器提供。
- 认证授权（FR7）尚未实现，M1 阶段接口为开放访问。

# 迷你 MES 系统（mes-platform）

> MES 自动化测试平台项目的 **M1 交付物**，作为整个项目的被测对象。
> 技术栈：Spring Boot 3.2.12 + JDK 17 + MyBatis-Plus 3.5.9 + MySQL 5.7。

本工程是测试链路中的被测系统。测试框架（`../mes-autotest`）以独立工程形式通过 HTTP 调用本服务接口，并直连 `mes_test` 库完成接口返回与落库的双向断言。两者分离的用意是保持断言的外部参照：测试与被测实现共处一个工程时，断言容易退化为对实现的重述。

---

## 1. 快速开始

### 1.1 环境要求

| 项 | 版本 | 参考路径（本机） |
|----|------|------------------|
| JDK | 17 | `C:\Users\Administrator\.jdks\temurin-17.0.20.1` |
| Maven | 3.9+ | 可使用 IDEA 内置版本 |
| MySQL | 5.7 | `C:\Program Files\MySQL\MySQL Server 5.7` |

### 1.2 初始化数据库

```bash
cd sql
mysql -uroot -p < 01_create_database.sql      # 建立 mes 与 mes_test 两个库
mysql -uroot -p mes < 02_schema_mes.sql       # 业务库建表
mysql -uroot -p < 03_schema_mes_test.sql      # 测试库建表
mysql -uroot -p mes < 04_seed_demo.sql        # 可选，导入演示数据
```

两个库表结构完全一致。业务库承载人工操作与演示数据，测试库仅供自动化用例使用，用例执行前后会自行造数与清场。

### 1.3 数据库凭据配置

凭据不写入仓库，通过环境变量提供；未设置时回落到本地开发默认值 `root/123456`。

```bash
set MES_DB_USER=root
set MES_DB_PASSWORD=<口令>
```

### 1.4 启动与自检

```bash
mvn spring-boot:run
# 或在 IDEA 中运行 MesPlatformApplication

curl http://localhost:8080/api/health      # 进程存活检测
curl http://localhost:8080/api/ready       # 就绪检测，含 MySQL 连通性，不通时返回 503
```

**profile 决定连接哪个数据库**，这一点在配合自动化测试时是关键。配置为 `${MES_PROFILE:dev}`，即默认使用 `dev`：

| profile | 连接的库 | 适用场景 |
|---------|----------|----------|
| `dev`（默认） | `mes` | 人工操作与界面演示 |
| `test` | `mes_test` | 执行自动化用例 |

```bash
export MES_PROFILE=test && mvn spring-boot:run      # 命令行方式
```

IDEA 中通过运行配置的 `Environment variables` 增加 `MES_PROFILE=test`（Spring Boot 类型的配置也可填在 `Active profiles` 一栏）。启动日志中出现以下内容即表示切换成功：

```
The following 1 profile is active: "test"
```

服务连错库时，测试框架会在开跑前终止并指出实际落点库，不会带着错误环境跑完 99 条用例再报一堆假失败。

| 入口 | 用途 |
|------|------|
| <http://localhost:8080/swagger-ui.html> | 接口文档，可直接编辑参数发起真实请求 |
| <http://localhost:8080/api/ready> | 就绪自检，反映数据库连通状态 |
| <http://localhost:8080/api/stats/overview> | 平台总览指标，单次请求可观察跨表聚合结果 |
| <http://localhost:8080/v3/api-docs> | OpenAPI 描述文件，供测试脚本核对接口契约 |

导入 `04_seed_demo.sql` 后，启动即可查询到工单、质检、批次与数采记录。

### 1.5 执行单元测试

```bash
mvn test
```

单元测试不依赖数据库，覆盖状态机与数量守恒等核心规则。

### 1.6 在 IntelliJ IDEA 中运行

工程已预置 `.idea/misc.xml`、`.idea/encodings.xml`、`.idea/compiler.xml`，将项目 SDK 锁定为 JDK 17 并开启 Lombok 注解处理（该目录已被 `.gitignore` 忽略，不进入仓库）。

1. `File` → `Open`，选择 `mes-platform` 目录（即 `pom.xml` 所在层级）
2. 出现 Trust Project 提示时选择信任
3. 提示 Maven 项目待导入时，选择 Load Maven Project
4. 核对 SDK：`File` → `Project Structure` → `Project`，SDK 应为 temurin-17，Language level 为 17。若显示为 1.8 需手动调整，JDK 版本不匹配是 Spring Boot 3 启动失败最常见的原因
5. 打开 `src/main/java/com/xwj/mes/MesPlatformApplication.java`，运行 `main` 方法
6. 控制台输出 `Started MesPlatformApplication` 表示启动成功，Tomcat 监听 8080 端口

编辑器提示找不到 `getXxx()` 方法但 Maven 编译通过时，说明 Lombok 注解处理未启用：`File` → `Settings` → `Build, Execution, Deployment` → `Compiler` → `Annotation Processors`，勾选 Enable annotation processing。

---

## 2. 接口契约

### 2.1 统一响应体

所有已路由至 Controller 的请求均返回 HTTP 200，业务结果由 `code` 字段承载。这一约定使测试脚本可以使用同一套断言模板处理全部接口。

```json
{
  "code": 0,
  "message": "成功",
  "data": { },
  "traceId": "a1b2c3d4e5f6a7b8",
  "timestamp": 1760700000000
}
```

| HTTP 状态 | 含义 | 出现场景 |
|-----------|------|----------|
| 200 | 请求已到达业务层 | 成功、参数校验失败、业务规则拒绝、业务语义上的资源不存在 |
| 404 | 路由或静态资源不存在 | 请求未匹配到任何接口 |
| 500 | 未预期异常 | 代码缺陷，凭 `traceId` 检索日志 |

`traceId` 同时写入响应头 `X-Request-Id`。调用方自带该请求头时原样沿用，便于将一次执行产生的多条请求日志串联起来。

### 2.2 业务状态码

| code | 含义 |
|------|------|
| 0 | 成功 |
| 40000 / 40001 | 参数校验失败 / 请求体格式错误 |
| 40400 | 资源不存在（业务语义） |
| 40900 / 40901 | 业务状态冲突 / 数据已存在 |
| 50000 / 50001 | 系统内部错误 / 数据库访问异常 |
| 50300 | 服务依赖不可用 |

将业务结果与传输状态解耦，好处在于测试用例可以只断言 `code`，不受 HTTP 语义灰度影响；代价是调用方必须显式检查 `code`，不能仅依赖传输层状态码判断成败。

### 2.3 接口清单

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health`、`/api/ready` | 存活与就绪自检 |
| POST | `/api/work-orders` | 创建工单 |
| GET | `/api/work-orders` | 分页查询（支持 status / lineCode / productCode / keyword） |
| GET | `/api/work-orders/{orderNo}` | 工单详情，含报工明细 |
| GET | `/api/work-orders/{orderNo}/reports` | 报工记录 |
| PUT | `/api/work-orders/{orderNo}/dispatch` | 派工 |
| POST | `/api/work-orders/{orderNo}/reports` | 报工 |
| PUT | `/api/work-orders/{orderNo}/close` | 关闭工单 |
| POST | `/api/quality-inspections` | 录入质检 |
| GET | `/api/quality-inspections` | 分页查询质检记录 |
| GET | `/api/quality-inspections/defects/{orderNo}` | 按工单追溯不良明细 |
| GET | `/api/quality-inspections/defect-summary` | 不良代码分布 |
| POST | `/api/material-batches` | 物料批次建档 |
| GET | `/api/material-batches` | 分页查询批次 |
| PUT | `/api/material-batches/{batchNo}/bind?orderNo=` | 批次绑定工单 |
| PUT | `/api/material-batches/{batchNo}/outbound` | 批次出货消耗 |
| GET | `/api/traces/batch/{batchNo}` | 正向追溯（批次 → 工单 → 节点流水） |
| GET | `/api/traces/order/{orderNo}` | 反向追溯（工单 → 批次 + 节点 + 不良明细） |
| POST | `/api/device-data`、`/api/device-data/batch` | 设备数采上报，单条或批量（上限 200） |
| GET | `/api/device-data`、`/api/device-data/abnormal` | 数采记录查询与异常数据捞取 |
| GET | `/api/stats/overview` | 平台总览指标 |
| GET | `/api/stats/production?from=&to=&lineCode=` | 产量日报，按日期与产线聚合 |
| GET | `/api/stats/yield/orders?limit=` | 低良率工单排行 |

---

## 3. 核心业务规则

以下规则是 M2 用例设计的蓝本，也是被测系统的约束边界。

### 工单状态机

```
NEW ──派工──▶ DISPATCHED ──首次报工──▶ IN_PROGRESS ──关闭──▶ CLOSED
                   │                        │
                   └────────关闭────────────┘
```

仅 `DISPATCHED` 与 `IN_PROGRESS` 允许报工，`NEW` 与 `CLOSED` 一律返回 40900。`NEW` 状态不允许关闭，`CLOSED` 状态不可重复关闭。

### 数量守恒

合格数与不良数之和必须等于报工数，质检同理。两者均不传时按全部合格处理，仅传其一则自动推算另一值。累计报工数超过计划数时直接返回 40900 拦截。

### 质检结论推导

结论由数量推导，不接受人工指定相反结论：不良数大于 0 即判定为 `FAIL`。存在不良时必须填写 `defectCode`，否则追溯链在不良环节断裂。

### 批次绑定约束

一个批次只允许绑定一个工单，重复绑定时返回 40900，防止追溯串线。状态为 `CONSUMED` 的批次不可再绑定或重复出货。

### 数采数据质量把关

设备上报的 `rawValue` 声明为字符串类型而非数值。现场设备上报畸形数据属于常态，入口不做类型强转，由业务层判定质量等级后落库，共分三层：

| 层级 | 判定条件 | 结果 |
|------|----------|------|
| 可解析性 | `rawValue` 无法转换为数值 | `BAD`，数值不入账，原始串保留 |
| 工况区间 | 温度不在 [-50, 200]℃、产量不在 [0, 1000000]、状态不在 [0, 10] | `SUSPECT`，数值仍留档 |
| 时间合理性 | 采集时间晚于当前时间 5 分钟以上 | `SUSPECT`，判定为设备时钟异常 |

不合格数据一律留痕，不做静默丢弃。相比让脏数据进入统计口径，保留原始记录以便事后排查是更可取的取舍。

---

## 4. 工程结构

```
src/main/java/com/xwj/mes/
├── MesPlatformApplication.java
├── common/                      # 跨模块基础设施
│   ├── api/                     # ApiResponse / PageResult / PageQuery / ErrorCode
│   ├── exception/               # BizException + GlobalExceptionHandler
│   ├── entity/BaseEntity.java   # 主键、审计时间、逻辑删除
│   ├── config/                  # MyBatis-Plus 插件、审计填充、CORS、OpenAPI、traceId 过滤器
│   ├── health/                  # /api/health 与 /api/ready
│   └── util/                    # 单据号生成、文本清洗
├── workorder/                   # 工单与报工：状态机、数量守恒
├── quality/                     # 质检：结论推导、不良追溯
├── material/                    # 物料批次与追溯流水：正反向追溯
├── device/                      # 设备数采：脏数据质量判定
└── stats/                       # 统计报表：聚合逻辑下沉至 SQL

sql/                             # 01 建库 → 02 业务库建表 → 03 测试库建表 → 04 演示数据
```

采用按业务域分包而非按技术层分包。新增业务模块时只需增加一个包，不需要改动框架层代码；模块内部的 Controller、Service、Mapper、DTO 自成一个闭合单元。

---

## 5. 实现说明

**统一响应与全局异常处理。** 业务异常统一由 `BizException` 携带错误码抛出，`GlobalExceptionHandler` 负责转换为统一响应体。参数校验失败由 `MethodArgumentNotValidException` 捕获后映射为 40000，避免校验信息以 500 形式泄漏到调用方。

**traceId 贯穿单次请求。** 过滤器在请求入口生成或沿用 `X-Request-Id`，写入 MDC 供日志输出，同时回写响应体与响应头。排查问题时凭响应中的 traceId 可直接定位到对应的日志片段。

**并发下的数量正确性。** 报工、派工、关闭等会修改工单数量的操作均在事务内先对工单行加锁（`SELECT ... FOR UPDATE`），再读取当前累计值并校验，避免两个并发报工请求同时通过超报校验。这一实现足以覆盖单机场景，分布式部署时需要补充其他机制。

**统计聚合下沉 SQL。** 总览、产量日报、良率排行等报表逻辑写在 Mapper 的 SQL 中，不在 Java 层做循环累加。好处是数据量增长时不必改动业务代码，口径也只在一处定义，与接口返回值天然一致。

---

## 6. 已知边界

- 定位为单机实践项目，未做高并发设计。并发正确性依靠工单行锁保证，未引入分布式锁
- 未接入真实 PLC 或产线设备，设备侧数据由 `../mes-simulator` 的 Modbus 从站提供
- 认证与授权尚未实现，接口为开放访问
- 未引入缓存层。统计接口每次请求实时聚合，当前数据量下响应时间在可接受范围内

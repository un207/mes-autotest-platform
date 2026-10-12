# MES 接口自动化测试框架（mes-autotest）

> MES 自动化测试平台项目的 **M2 交付物**，被测对象为 `../mes-platform`。
> 技术栈：pytest 9.1.1 + requests 2.34.2 + PyYAML 6.0.3 + PyMySQL + Allure（软依赖）。

本工程是被测系统的外部验证者。两者独立成工程，出于一个直接的考虑：测试与被测实现放在一起时，断言往往退化为对实现逻辑的重述，无法发现实现本身的错误。分离之后，测试只能通过 HTTP 接口和数据库这两个外部视角观察系统，断言的参照系才成立。

---

## 1. 与 MES 的对接方式

测试框架与 MES 之间存在三条对接通道，分别承担不同职责。

### 通道一：HTTP 接口（主通道）

框架通过 HTTP 调用被测系统接口完成业务操作。对接建立在两项契约之上。

**统一响应体契约。** MES 所有已路由请求均返回 HTTP 200，业务结果由 `code` 字段承载（0 成功，40000 参数校验失败，40400 资源不存在，40900 状态冲突）。框架的 `common/http_client.py` 对这一约定做了一次封装：`code != 0` 统一转为异常抛出，用例只需处理成功与失败两个分支，不必在每个断言里重复判断状态码。

**接口路径集中登记。** 24 个接口路径统一登记在 `config/endpoints.yml`，用例代码不出现字面量 URL。接口路径调整时只修改该文件，用例脚本不受影响。

```yaml
# config/endpoints.yml 节选
work_orders: /api/work-orders
work_order_reports: /api/work-orders/{orderNo}/reports
device_data: /api/device-data
```

### 通道二：数据库直连（校验通道）

`common/db_client.py` 以 PyMySQL 直连 `mes_test` 库，用于两类场景：验证接口操作是否真正持久化，以及执行造数与清场。

这条通道是双向断言的实现基础。仅断言接口返回值不足以确认数据正确落库——事务可能未提交、字段可能映射错误、级联写入可能遗漏，这些情况在响应体上都表现为成功。

```python
reported = factory.report(order_no, report_qty=120, qualified=115, defective=5)
assert_fields(reported, status="IN_PROGRESS", finishedQty=120)       # 接口返回正确

row = db.get_row("mes_work_order", {"order_no": order_no})
assert_true(row["finished_qty"] == 120, "库中累计报工数应为 120")      # 数据库同样正确
assert_true(db.count("mes_work_report", {"order_no": order_no}) == 1,
            "应恰好产生 1 条报工记录")                                 # 级联写入未遗漏
```

### 通道三：契约核对接口

`/v3/api-docs` 提供 OpenAPI 描述文件，服务自检用例读取后与框架内登记的接口清单做交叉校验。接口被重命名或删除而框架未同步时，自检阶段即会失败，不必等到具体用例报错。

### 对接前的环境校验

对接正确性依赖一个前提：接口实际写入的库，与框架回查的库是同一个。框架在会话开始时强制校验两件事，任一不通过立即终止：

1. 配置中的库名必须以 `_test` 结尾
2. 通过接口创建一条工单，再直连数据库确认可查询到

第二项校验同时验证了「HTTP 通道可达」与「数据库通道指向同一实例」。缺少这层校验时，接口连向业务库而框架查询测试库的情况下，用例会跑完全部 99 条再报出大量难以定位的假失败。

---

## 2. 用例设计方法

### 分层依据

99 条用例按被测对象的能力边界划分，各层关注不同风险：

| 模块 | 条数 | 设计意图 |
|------|------|----------|
| 服务自检 | 3 | 环境与契约正确性，作为其余用例的前置条件 |
| 工单主链路 | 1 | 端到端流程贯通，验证模块间协作 |
| 工单业务规则 | 36 | 单条规则的正向、反向与边界覆盖 |
| 质量检验规则 | 19 | 结论推导的推导正确性与必填约束 |
| 物料批次与追溯 | 10 | 状态流转与防串线约束 |
| 设备数采质量 | 24 | 三层质量把关的判定准确性 |
| 统计报表 | 6 | 聚合口径与筛选条件正确性 |

### 四类设计手法

**等价类划分。** 数量守恒规则中，「合格数 + 不良数 = 报工数」是合法类，「两者之和小于报工数」「大于报工数」分别构成两个非法类，各自独立成例，而非只验证其中一种。

**边界值分析。** 计划数量、分页大小、批量上报条数等带上下限的参数按边界取值：恰好等于下限、恰好等于上限、上限加一、下限减一。分页参数另外覆盖了负数与超出上限的取值。

**状态机全覆盖。** 工单状态机的三条合法迁移路径各有一个正向用例；四条非法迁移（`NEW` 直接报工、`NEW` 直接关闭、`CLOSED` 重复关闭、`CLOSED` 再次报工）各自有对应的拦截用例。合法路径确保功能可用，非法路径确保约束生效，两者缺一不可。

**数据驱动。** 同一逻辑、不同输入的场景不重复写用例方法，改为在 YAML 中追加数据行：

```yaml
qty_conservation:
  - id: mismatch-defective
    desc: 合格数 + 不良数 小于报工数，应拒绝
    plan_qty: 500
    report_qty: 100
    qualified: 60
    defective: 30
    expect_code: 40000
```

新增同类场景只增加数据，不需要改动测试代码，也避免了相似用例之间的实现漂移。

### 断言设计

断言失败信息包含完整的现场上下文，包括请求方法、URL、响应状态码、业务码、traceId、耗时与响应体。traceId 与 MES 服务日志中的标识一致，凭此可直接定位到对应的服务端日志片段。

```
[工单报工] 期望业务码 40900，实际 0 message='成功'
  POST http://127.0.0.1:8080/api/work-orders/WO2026.../reports | HTTP=200 code=0
  | traceId=ab6f37e8bdeb4ee8 | 耗时=4ms | body={"code":0,...}
```

若失败信息只输出「期望 40900 实际 0」，排查时需要重新构造请求、复现问题、再翻日志查找，成本远高于一次断言中带上全部信息。

---

## 3. 框架结构

### 三层解耦

```
用例层 testcases/     只描述场景与期望，不涉及请求构造细节
   ↓
封装层 common/        负责发请求、连库、造数、断言
   ↓
配置层 config/        承载地址、超时、数据库连接、口径阈值
```

分层的收益体现在变更成本上：接口地址调整只改 `endpoints.yml`，环境切换只改 `env.yml` 或用环境变量覆盖，用例脚本在这两类变更下都不需要修改。

### 目录结构

```
mes-autotest/
├── pytest.ini                  # 标记定义与默认参数
├── requirements.txt            # 依赖及版本
├── config/
│   ├── env.yml                 # 环境配置：base_url、超时、数据库、造数前缀
│   └── endpoints.yml           # 24 个接口路径集中登记
├── common/                     # 公共封装，用例只依赖这一层
│   ├── config_loader.py        # 配置加载，敏感项支持环境变量覆盖
│   ├── http_client.py          # requests 封装与统一响应模型 ApiResult
│   ├── db_client.py            # PyMySQL 封装，用于落库校验与清场
│   ├── data_factory.py         # 造数工厂：唯一编码、登记、清场联动
│   ├── assert_helper.py        # 断言助手，失败信息自带 traceId
│   └── report.py               # Allure 适配层，未安装时静默降级
├── data/                       # YAML 数据驱动用例数据
│   ├── work_order_rules.yml
│   ├── work_order_param.yml
│   ├── quality_rules.yml
│   └── device_data_rules.yml
├── testcases/                  # 用例与夹具
│   ├── conftest.py             # 环境前置检查、会话夹具、清场与历史留档
│   ├── test_health.py
│   ├── test_work_order_lifecycle.py
│   ├── test_work_order_rules.py
│   ├── test_quality_rules.py
│   ├── test_material_trace.py
│   ├── test_device_data.py
│   └── test_stats.py
├── history/
│   └── api-test-history.jsonl  # 执行历史，随仓库提交，趋势数据源
├── tools/
│   ├── run.py                  # 一键：等待就绪 → 执行用例 → 生成三类报告
│   ├── wait_ready.py           # 轮询就绪接口，超时给出排查方向
│   ├── report_html.py          # junit.xml 转 HTML 报告
│   └── trend.py                # 执行历史转通过率趋势页
└── reports/                    # 一次性产物，已 gitignore
```

### 数据可重复与自动清场

自动化用例反复执行的前提是数据不冲突、不留残留，因此设计了三项机制。

**唯一编码。** 所有业务编码携带当轮唯一前缀（形如 `M210121330-001`），重复执行不会撞唯一键，也不会覆盖上一轮数据。

**登记式清场。** 造出的单号全部登记，会话结束时统一删除，无论用例成败都执行。排障时可设置 `MES_TEST_CLEANUP=false` 关闭清场以保留现场。

**兜底扫描。** 按登记单号精确删除之后，再按当轮时间窗扫描一次，捞取绕过工厂直接调用接口产生的数据。兜底扫描命中时框架会在输出中提示，说明有用例未走工厂方法，属于需要修正的写法。

### 前置检查

`conftest.py` 在会话开始时校验环境：被测服务可达、数据库可连、库名合规、接口写入库与校验库一致。任何一项不通过即终止执行并输出排查方向。检查失败的用例集不输出 99 条失败记录，只输出一条明确的环境问题——环境不通时逐条报错会把真正的原因淹没在噪音里。

---

## 4. 执行方式

### 前置条件

| 项 | 要求 |
|----|------|
| Python | 3.13 及以上 |
| 依赖 | `pip install -r requirements.txt` |
| 被测服务 | `../mes-platform` 已启动，且必须为 test profile |
| MySQL | 5.7，需存在 `mes_test` 库 |

启动被测服务并切换 profile：

```bash
cd ../mes-platform
export MES_PROFILE=test
mvn spring-boot:run
```

`MES_PROFILE=test` 决定数据写入 `mes_test` 还是 `mes`。用例会造数并清场，只允许对测试库操作，框架的前置校验会强制这一点。

### 常用命令

```bash
pytest                                     # 全量 99 条
pytest -m smoke                            # 冒烟 10 条
pytest -m regression                       # 业务规则回归 89 条
pytest -m db                               # 需要数据库直连的 60 条
pytest -m "not db"                         # 不需要数据库的 39 条
pytest testcases/test_work_order_lifecycle.py   # 指定文件

# 生成 junit 与 allure 原始结果
pytest --junitxml=reports/junit.xml --alluredir=reports/allure-results
```

### 一体化执行

`tools/run.py` 将等待就绪、执行用例、生成报告串联为一次操作，避免手工执行时遗漏出报告环节：

```bash
python tools/run.py                          # 连接已启动的服务，执行全量并出报告
python tools/run.py --start-app              # 自动构建并启动被测服务，跑完自动停止
python tools/run.py --scope smoke            # 仅执行冒烟
python tools/run.py --label <来源标识>        # 标记执行来源，写入趋势记录
```

脚本结束时会逐项打印产物的实际存在状态，不会在报告生成失败时输出成功提示。

### 报告产物

| 产物 | 位置 | 用途 |
|------|------|------|
| 自制 HTML 报告 | `reports/测试报告.html` | 分模块通过率与失败明细，零依赖，可打印为 PDF |
| 通过率趋势 | `reports/通过率趋势.html` | 跨轮次通过率折线，失败轮次标红 |
| Allure 报告 | `reports/allure-report/index.html` | 含执行步骤与请求响应附件，适合排查单条用例 |
| JUnit XML | `reports/junit.xml` | 供 CI 平台消费的机器可读结果 |

Allure 报告为单页应用，受浏览器同源策略限制无法直接双击打开，需以静态服务方式访问：

```bash
../.tools/allure-2.46.1/bin/allure.bat open reports/allure-report
python -m http.server 9000 --directory reports/allure-report   # 或使用任意静态服务器
```

---

## 5. 执行历史与通过率趋势

每轮执行结束后，`common/history.py` 向 `history/api-test-history.jsonl` 追加一条记录：

```json
{"ts":"2026-10-12T13:38:04+08:00","time":"2026-10-12 13:38:04","run_id":"20261012133804",
 "label":"local-full","host":"WIN-JDF6FLM04TD","total":99,"passed":99,"failed":0,"error":0,
 "duration":19.925,"pass_rate":100.0}
```

该文件随仓库提交，与可随时删除的 `reports/` 区分开。趋势的价值来自跨轮次、跨机器的累积，因此记录必须持久化。CI 每轮结束后会把新记录回写仓库，本机与 CI 的执行记录因此汇入同一条趋势线。

记录中同时保留 `ts` 与 `time` 两个时间字段，原因是执行环境分布在两个时区：

| 字段 | 用途 |
|------|------|
| `ts` | 带时区偏移，作为排序与比较的依据。CI runner 使用 UTC，本机使用 UTC+8，仅按本地时间字符串排序会把 CI 记录排到最早 |
| `time` | 供阅读的北京时间，由 `ts` 换算得到，避免同一份趋势中时间忽早忽晚 |

```bash
python tools/trend.py                       # 渲染趋势页
python tools/trend.py --limit 30            # 仅取最近 30 轮
MES_HISTORY_FILE=<路径> python tools/trend.py   # 指向其他历史文件，用于试跑验证
```

趋势页使用手写 SVG 渲染，不引入图表库或 CDN 依赖，可离线打开与打印。

---

## 6. 扩展用例

**新增规则分支** —— 在 `data/*.yml` 中追加一条数据，无需改动代码。

**新增接口** —— 先在 `config/endpoints.yml` 登记路径，再在对应 `testcases/test_*.py` 中编写用例。

**新增造数场景** —— 统一通过 `factory` 提供的方法（`create_order`、`create_dispatched_order`、`create_in_progress_order`、`create_batch`）。绕过工厂直接调用接口造出的数据不会被登记，只能依靠兜底扫描清理，且无法保证清场完整性。

**新增断言** —— 使用 `common/assert_helper.py` 中的助手，失败信息自带 traceId 与响应体，保持全项目断言输出格式一致。

---

## 7. 持续集成

流水线定义于仓库根的 `.github/workflows/api-test.yml`。

### 执行流程

```
检出代码
  → 安装 JDK 17 与 Python 3.13（均启用依赖缓存）
  → 启动 MySQL 5.7 容器（与本地版本一致）
  → 建库建表（mes 与 mes_test）
  → mvn package 构建被测系统
  → 以 test profile 启动被测系统，轮询 /api/ready 等待就绪
  → pytest 执行用例，tee 保存完整输出
  → 生成 Allure 报告、自制 HTML 报告与通过率趋势
  → 回写执行历史
  → 三类报告与执行历史作为 artifact 上传，保留 30 天
```

### 触发方式

| 事件 | 行为 |
|------|------|
| 推送或拉取请求 | 按路径过滤后全量回归 |
| 手动触发 | 可选全量或仅冒烟 |
| 定时（每日北京时间 06:00） | 全量回归，用于发现环境漂移引起的慢性问题 |

路径过滤的范围为 `mes-platform/**`、`mes-autotest/**`、`mes-simulator/**`、`mes-console/**` 以及工作流文件本身。仅修改文档不会触发流水线。

### 执行历史回写

流水线在生成报告后将执行历史提交回仓库，提交信息带跳过 CI 的标记以避免自触发：

```
生成报告 → git add history/api-test-history.jsonl
        → 检测到变化时提交并推送，无变化则跳过
```

这一步骤为必需项。缺少回写时，CI 产生的记录仅存在于 artifact 中，30 天后随 artifact 过期消失，趋势累积在 CI 侧实际不成立。

该步骤需要 `permissions: contents: write`，已在工作流中声明。仓库启用分支保护时自动提交会被拒绝，此时应改为仅上传 artifact。

### 一个需要留意的行为

GitHub 扫描整条提交信息（标题与正文）来识别跳过 CI 的标记，不限于标题。因此在其他提交的正文中提及该标记时，那一轮流水线同样会被静默跳过——没有报错也没有提示，只表现为 Actions 页面少了一次运行记录。撰写提交信息与文档时需注意避免。

### CI 与本地的一致性

同一份用例与断言在两类环境中执行，因此刻意对齐了两处易产生偏差的地方：

- **MySQL 使用 5.7 而非 8.0**，与本地保持一致，避免出现本地通过而 CI 失败的版本差异
- **被测系统强制使用 test profile**，框架的前置校验会交叉验证接口实际写入的库

---

## 8. 已知限制

- 用例按单机顺序执行设计，不支持多轮并发执行，清场的时间窗兜底基于该假设，CI 中同样串行执行
- 报表类断言与库中全量数据比对。库中存在其他来源的数据时比对仍然成立（两侧口径一致），但残留数据会干扰失败信息阅读
- Allure 报告需以静态服务方式访问，自制 HTML 报告与趋势页无此限制
- 未覆盖性能与并发场景，相关内容规划在 M5

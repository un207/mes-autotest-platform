# MES 自动化测试框架（mes-autotest）

> MES 场景自动化测试平台项目的 **M2 交付物**：接口自动化测试框架与用例库。
> 技术栈：pytest 9.1.1 + requests 2.34.2 + PyYAML 6.0.3 + PyMySQL + Allure（软依赖）。

本工程是**测试方**，被测对象是隔壁的 `../mes-platform`（迷你 MES 系统）。两者严格分离 ——
业务系统与测试框架混在一起就变成「自己测自己」，逻辑上不成立。

---

## 1. 快速开始

### 1.1 前置条件

| 项 | 要求 |
|----|------|
| Python | 3.13+（本机用 `C:\Users\Administrator\.workbuddy\binaries\python\envs\default`） |
| 依赖 | `pip install -r requirements.txt` |
| 被测服务 | `../mes-platform` 已启动，且**切换为 test profile** |
| MySQL | 5.7，需有 `mes_test` 库（执行过 mes-platform 的 `sql/01` 与 `sql/03`） |

### 1.2 启动被测服务（关键：必须用 test profile）

```bash
cd ../mes-platform
unset SERVER__PORT SERVER__HOST          # WorkBuddy 沙箱特有，IDEA/CMD 里不需要
export JAVA_HOME="C:/Users/Administrator/.jdks/temurin-17.0.20.1"
export MES_PROFILE=test                  # ← 决定数据写进 mes_test 还是 mes
mvn spring-boot:run
```

> 为什么要切 profile：用例会造数并清场，**只允许对测试库动手**。
> 框架在开跑前会做两道校验 —— 配置里的库名必须以 `_test` 结尾，且会用接口建一条工单再回测试库确认能找到；
> 任何一道不过，直接终止并提示，不会带着错的环境跑完 99 条用例再报一堆假失败。

### 1.3 跑用例

```bash
# 全量（99 条）
pytest

# 只跑冒烟（10 条，CI 每次提交用）
pytest -m smoke

# 只跑业务规则回归（89 条）
pytest -m regression

# 排除需要落库校验的用例（不需要数据库也能跑，39 条）
pytest -m "not db"

# 需要数据库直连的用例
pytest -m db

# 指定单条
pytest testcases/test_work_order_lifecycle.py

# 出报告（junit + allure 原始结果）
pytest --junitxml=reports/junit.xml --alluredir=reports/allure-results

# 渲染一份人能读的 HTML 报告（零依赖，双击即开）
python tools/report_html.py
```

### 1.4 一键跑（推荐日常用）

上面那些命令分散着敲容易漏掉出报告这一步。一体化脚本把「等就绪 → 跑用例 → 出三种报告」串起来：

```bash
# 连已在跑的服务，跑全量并出全部报告
python tools/run.py

# 自动构建并启动被测服务（test profile），跑完自动停掉
python tools/run.py --start-app

# 只跑冒烟
python tools/run.py --scope smoke --label 快速验证

# 标记执行来源（会记进趋势，便于区分谁跑的）
python tools/run.py --label 张三-本机
```

跑完会打印三份产物的**真实存在状态**（`[OK]` / `[缺失]`），不存在脚本不会谎报成功。

### 1.5 看报告

| 产物 | 位置 | 用途 |
|------|------|------|
| 自制 HTML 报告 | `reports/测试报告.html` | 分模块通过率 + 失败明细。零依赖，可打印成 PDF |
| 通过率趋势 | `reports/通过率趋势.html` | 跨轮次通过率折线，失败轮次标红 |
| Allure 报告 | `reports/allure-report/index.html` | 带步骤与请求/响应附件，排查单个用例最方便。**需起本地服务打开**（见下） |
| JUnit XML | `reports/junit.xml` | 给 CI 平台消费的机器可读结果 |

Allure 报告是 SPA，直接双击 `index.html` 会因浏览器同源策略读不到数据，需起个静态服务：

```bash
# 方式一：用 Allure 自带命令（它会起服务并打开浏览器）
../.tools/allure-2.46.1/bin/allure.bat open reports/allure-report

# 方式二：任意静态服务器
python -m http.server 9000 --directory reports/allure-report
```

### 1.6 通过率趋势怎么来的

每跑一轮（无论成功失败），`common/history.py` 会往 `history/api-test-history.jsonl` 追加一条摘要：

```json
{"ts":"2026-10-12T13:38:04+08:00","time":"2026-10-12 13:38:04","run_id":"20261012133804",
 "label":"local-full","host":"WIN-JDF6FLM04TD","total":99,"passed":99,"failed":0,"error":0,
 "duration":19.925,"pass_rate":100.0}
```

这个文件**进版本控制**（与随时可删的 `reports/` 不同）—— 趋势的价值就在于跨轮次、跨机器累积。
CI 每跑完一轮也会把它回写仓库（见第 6 节），所以本机与 CI 的记录汇在同一条趋势线上。

**两个字段为什么都要**：

| 字段 | 用途 |
|------|------|
| `ts` | 带时区偏移，**排序与跨时区比较的依据**。CI runner 在 UTC、本机在 UTC+8，只靠本地时间字符串排序会把 CI 那轮排到最早 |
| `time` | 供人阅读的**北京时间**。同一次执行在 CI 上记录为 UTC，展示时统一转成北京时间，避免同一份趋势里时间忽早忽晚 |

```bash
python tools/trend.py                    # 渲染趋势页
python tools/trend.py --limit 30         # 只看最近 30 轮
MES_HISTORY_FILE=其他路径.jsonl python tools/trend.py   # 指向别的历史文件（用于试跑验证）
```

排障时想保留现场，别让框架清场：

```bash
MES_TEST_CLEANUP=false pytest testcases/test_work_order_rules.py
```

---

## 2. 目录结构

```
mes-autotest/
├── pytest.ini                  # 标记定义与默认参数
├── requirements.txt            # 依赖及版本（与本机 venv 实测一致）
├── config/
│   ├── env.yml                 # 环境配置：base_url / 超时 / 数据库 / 造数前缀
│   └── endpoints.yml           # 24 个接口路径集中登记
├── common/                     # 公共封装（用例只 import 这一层）
│   ├── config_loader.py        # 配置加载，敏感项支持环境变量覆盖
│   ├── http_client.py          # requests 封装 + 统一响应模型 ApiResult
│   ├── db_client.py            # pymysql 封装，落库校验与清场专用
│   ├── data_factory.py         # 造数工厂：唯一编码 + 登记 + 清场
│   ├── assert_helper.py        # 断言助手，失败信息自带 traceId
│   └── report.py               # Allure 适配层（未装 allure 时静默降级）
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
│   └── api-test-history.jsonl  # 执行历史（进版本控制，趋势数据源）
├── tools/
│   ├── run.py                  # 一键：等就绪 → 跑用例 → 出三种报告
│   ├── wait_ready.py           # 轮询就绪接口（替掉 sleep，失败给排查指引）
│   ├── report_html.py          # junit.xml → HTML 报告
│   └── trend.py                # 执行历史 → 通过率趋势页
└── reports/                    # 一次性产物（已 gitignore）
```

---

## 3. 框架设计要点

### 3.1 三层解耦

```
用例层 testcases/   —— 只写「场景与期望」，不写请求细节
   ↓
封装层 common/      —— 发请求、连库、造数、断言
   ↓
配置层 config/      —— 地址、超时、库连接、口径阈值
```

接口地址一改只动 `endpoints.yml`；换环境只改 `env.yml` 或用环境变量；用例脚本不动。

### 3.2 「接口返回 + 落库」双重断言

只说接口 200 是假测试 —— 接口返回成功不代表数据真写进库了。所以关键用例都多做一步直连校验：

```python
reported = factory.report(order_no, report_qty=120, qualified=115, defective=5)
assert_fields(reported, status="IN_PROGRESS", finishedQty=120)      # ① 接口返回对

row = db.get_row("mes_work_order", {"order_no": order_no})
assert_true(row["finished_qty"] == 120, ...)                        # ② 库里也要对
assert_true(db.count("mes_work_report", {"order_no": order_no}) == 1, ...)
```

### 3.3 数据可重复与自动清场

- **可重复**：所有编码带本轮唯一前缀（形如 `M210121330-001`），反复跑不撞唯一键、不影响上一轮
- **自动清场**：造出的单号全部登记，会话结束统一清理（无论用例成败）
- **两层清理**：按登记单号精确删 → 再按本轮时间窗兜底扫一遍，捞住「绕过工厂直接调接口」造出的数据
- **安全护栏**：库名不以 `_test` 结尾直接拒绝执行

### 3.4 失败信息自带 traceId

每个断言失败都会带上完整上下文，不用再去翻日志：

```
[工单报工] 期望业务码 40900，实际 0 message='成功'
  POST http://127.0.0.1:8080/api/work-orders/WO2026.../reports | HTTP=200 code=0
  | traceId=ab6f37e8bdeb4ee8 | 耗时=4ms | body={"code":0,...}
```

`traceId` 就是 MES 服务日志里那一条的标识，直接搜即可定位。

### 3.5 数据驱动

负向规则、边界值这类「同一逻辑、不同输入」的用例全部走 YAML，新增一条只加数据不改代码：

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

---

## 4. 用例清单（99 条）

| 模块 | 条数 | 覆盖内容 |
|------|------|----------|
| 服务自检 | 3 | 存活/就绪、接口与直连的库版本交叉校验、未知路由 404 |
| 工单主链路 | 1 | 建单→派工→批次→报工→质检→双向追溯→关闭，每步含落库断言 |
| 工单业务规则 | 36 | 数量守恒、数量推算、超报拦截、状态机、计划时间、参数校验、分页边界 |
| 质量检验规则 | 19 | 结论推导、不良代码必填、结论矛盾、数量守恒、工单/批次关联、不良追溯、分页筛选 |
| 物料批次与追溯 | 10 | 批次状态流转、绑定与改绑、出货、冻结拦截、重复批次号、双向追溯、节点顺序 |
| 设备数采质量 | 24 | 三层把关（可解析性/工况区间/时间合理性）、批量边界、参数校验、异常数据捞取 |
| 统计报表 | 6 | 总览口径反算、产量日报区间与产线筛选、低良率排行、参数边界 |

**标记分布**：`smoke` 10 条 · `regression` 89 条 · `db` 60 条（数字为实测，非估算）

---

## 5. 怎么加用例

1. **改规则分支** → 往 `data/*.yml` 加一条数据即可，不用动代码
2. **加新接口** → 先在 `config/endpoints.yml` 登记路径，再在对应 `testcases/test_*.py` 里写用例
3. **造数** → 一律走 `factory`（`create_order` / `create_dispatched_order` / `create_in_progress_order` / `create_batch`），
   绕开它直接调接口造的数据不会被登记，只能靠兜底扫描清掉
4. **断言** → 用 `common/assert_helper.py` 里的助手，失败信息自带上下文

---

## 6. 持续集成（M3）

流水线定义在仓库根的 `.github/workflows/api-test.yml`，每次推送/PR 自动跑。

### 6.1 流水线做什么

```
检出代码
  → 装 JDK 17 / Python 3.13（带依赖缓存）
  → 起 MySQL 5.7 容器（与本地同大版本，避免兼容性假失败）
  → 建库建表（mes + mes_test）
  → mvn package 构建被测系统
  → 以 test profile 启动被测系统，轮询 /api/ready 等就绪
  → pytest 跑用例（tee 保存完整输出）
  → 生成 Allure 报告 + 自制 HTML 报告 + 通过率趋势
  → 三份报告与执行历史作为 artifact 上传（保留 30 天）
```

### 6.2 触发方式

| 事件 | 行为 |
|------|------|
| push / PR（仅限 `mes-platform/**`、`mes-autotest/**`、workflow 自身变动） | 全量回归 |
| 手动触发（workflow_dispatch） | 可选 `all` 或 `smoke` |
| 定时（每天北京时间 06:00） | 全量回归，用于发现环境漂移导致的慢性问题 |

改文档不会触发流水线 —— 没必要为一次 README 改动烧 runner 额度。

### 6.3 趋势在 CI 上怎么累积

流水线在生成报告后会**把执行历史回写仓库**（提交信息带 `[skip ci]`，避免自己再触发一轮）：

```
生成报告 → git add history/api-test-history.jsonl
        → 有变化才提交并推送（无变化跳过）
```

为什么必须回写：否则 CI 跑出的记录只存在 artifact 里，30 天后随 artifact 过期消失，
「趋势随仓库累积」这件事对 CI 而言就不成立。

> 这一步需要 `permissions: contents: write`，已在 workflow 里声明。
> 若仓库开启了分支保护，自动提交会被拒绝 —— 那种情况下把这一步改成只上传 artifact 即可。

### 6.4 CI 与本地的一致性

同一份用例、同一套断言，CI 只是换了执行环境。刻意对齐了两处容易出偏差的地方：

- **MySQL 用 5.7**（不是 8.0）—— 与本机一致，避免「本地过、CI 挂」这类最难查的问题
- **被测服务必须用 test profile** —— 框架会前置校验「接口建的单在测试库能否查到」，不一致直接终止

---

## 7. 怎么加用例

1. **改规则分支** → 往 `data/*.yml` 加一条数据即可，不用动代码
2. **加新接口** → 先在 `config/endpoints.yml` 登记路径，再在对应 `testcases/test_*.py` 里写用例
3. **造数** → 一律走 `factory`（`create_order` / `create_dispatched_order` / `create_in_progress_order` / `create_batch`），
   绕开它直接调接口造的数据不会被登记，只能靠兜底扫描清掉
4. **断言** → 用 `common/assert_helper.py` 里的助手，失败信息自带 traceId 与响应体

---

## 8. 已知限制

- 用例按单机顺序执行设计，**不支持并发跑多轮**（清场的兜底时间窗基于此假设）；因此 CI 里也串行执行
- 汇总类断言（如统计报表）与库中全量数据比对。库里有别处数据时比对仍成立（两边口径一致），但残留数据会干扰阅读
- 设备模拟器、性能压测不在本工程范围（M4/M5）
- Allure 报告是 SPA，**必须起静态服务才能看**（`allure open` 或 `python -m http.server`），不能双击打开；
  自制 HTML 报告与趋势页则无此限制

---

## 9. 交付进度

| 阶段 | 内容 | 状态 |
|------|------|------|
| M1 | 迷你 MES 后端（被测对象） | ✅ 完成 |
| **M2** | **pytest 框架 + 99 条用例 + 落库双重断言** | ✅ **完成** |
| **M3** | **GitHub Actions 回归 + Allure 报告 + 通过率趋势** | ✅ **完成**（流水线未在真实 runner 上跑过，见下） |
| M4 | 设备模拟器（pymodbus）+ 管理界面 | 待开始 |
| M5 | 性能压测 / MQ（可选） | 待开始 |

> **M3 的验证边界（如实说明）**：流水线 YAML 的每一步都在本机按同样命令真跑过，
> 但尚未在 GitHub 的真实 runner 上执行过 —— 那需要一个已推送的 GitHub 仓库。
> 首次推送后如有失败，多半是路径或 runner 环境差异，按日志调整即可。

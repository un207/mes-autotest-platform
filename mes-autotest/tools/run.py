"""本地一体化执行：跑用例 → 出报告 → 出趋势。

CI 与本机共用同一套步骤，差别只在「谁负责启动被测服务」：
  - CI 里由流水线构建并启动（见 .github/workflows/api-test.yml）
  - 本机加 --start-app 让脚本自己拉起，不加则连已经在跑的服务

用法：
    python tools/run.py                      # 连已启动的服务，跑全量
    python tools/run.py --scope smoke        # 只跑冒烟
    python tools/run.py --start-app          # 自动启动被测服务（test profile）
    python tools/run.py --label my-branch    # 标记执行来源，趋势图上能区分开
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent          # mes-autotest/
WORKSPACE = ROOT.parent                                 # 工作区根（含 mes-platform）
PLATFORM = WORKSPACE / "mes-platform"
PYTHON = sys.executable

# 本机默认位置，允许用环境变量覆盖（换机器时不必改脚本）
DEFAULT_JAVA_HOME = r"C:/Users/Administrator/.jdks/temurin-17.0.20.1"
DEFAULT_MVN = (
    r"C:/Users/Administrator/.m2/wrapper/dists/apache-maven-3.9.14-bin/"
    r"1cb7fhup6b5n3bed6kckbrnspv/apache-maven-3.9.14/bin/mvn.cmd"
)


def log(msg: str) -> None:
    print(f"\n=== {msg} ===", flush=True)


def run(cmd: list[str], cwd: Path | None = None, env: dict | None = None) -> int:
    printable = " ".join(f'"{c}"' if " " in c else c for c in cmd)
    print(f"$ {printable}", flush=True)
    return subprocess.call(cmd, cwd=str(cwd) if cwd else None, env=env)


def start_app(profile: str) -> subprocess.Popen:
    """构建并启动被测系统，返回进程句柄。"""
    java_home = os.getenv("JAVA_HOME", DEFAULT_JAVA_HOME)
    mvn = os.getenv("MES_MVN", DEFAULT_MVN)

    env = dict(os.environ)
    env["JAVA_HOME"] = java_home
    # 沙箱会注入 SERVER__PORT，会被 Spring 的宽松绑定当成 server.port，必须清掉
    env.pop("SERVER__PORT", None)
    env.pop("SERVER__HOST", None)
    env["MES_PROFILE"] = profile

    log("构建被测系统（跳过其自带单测）")
    if run([mvn, "-B", "-ntp", "package", "-DskipTests"], cwd=PLATFORM, env=env) != 0:
        print("构建失败，终止", file=sys.stderr)
        sys.exit(2)

    jars = sorted((PLATFORM / "target").glob("mes-platform-*.jar"))
    if not jars:
        print("没找到构建产物 jar", file=sys.stderr)
        sys.exit(2)
    jar = jars[0]
    print(f"启动 jar: {jar.name}", flush=True)

    log_file = open(WORKSPACE / "app-local.log", "w", encoding="utf-8")  # noqa: SIM115
    java_bin = str(Path(java_home) / "bin" / ("java.exe" if os.name == "nt" else "java"))
    proc = subprocess.Popen(
        [java_bin, "-jar", str(jar)],
        cwd=str(PLATFORM),
        env=env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
    )
    print(f"PID={proc.pid}，日志：{WORKSPACE / 'app-local.log'}", flush=True)
    return proc


def main() -> int:
    parser = argparse.ArgumentParser(description="本地一体化跑测试并出报告")
    parser.add_argument("--scope", choices=["all", "smoke"], default="all")
    parser.add_argument("--label", default="local", help="执行来源标记，写入趋势")
    parser.add_argument("--start-app", action="store_true", help="自动启动被测服务")
    parser.add_argument("--profile", default="test", help="启动被测服务时使用的 profile")
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--timeout", type=int, default=180, help="等待服务就绪的秒数")
    args = parser.parse_args()

    env = dict(os.environ)
    env["MES_RUN_LABEL"] = args.label
    # JAVA_HOME 必须显式设上：Allure CLI 是 Java 程序，找不到 java 会静默失败
    # （allure.bat 报错后退出码仍是 0，不检查返回码就会误报「报告已生成」）
    env.setdefault("JAVA_HOME", DEFAULT_JAVA_HOME)
    if args.base_url:
        env["MES_BASE_URL"] = args.base_url

    reports = ROOT / "reports"
    reports.mkdir(exist_ok=True)

    proc = None
    try:
        # ---------------------------------------------------------- 启动被测系统
        if args.start_app:
            proc = start_app(args.profile)

        # 无论服务是自己起的还是别人起的，都先确认就绪 ——
        # 对着半死的服务跑用例，只会得到一堆看不懂的失败
        log("等待被测服务就绪")
        wait_cmd = [PYTHON, str(ROOT / "tools" / "wait_ready.py"), "--timeout", str(args.timeout)]
        if args.base_url:
            wait_cmd += ["--url", args.base_url]
        if run(wait_cmd, cwd=ROOT, env=env) != 0:
            print("服务未就绪，终止", file=sys.stderr)
            return 2

        # ---------------------------------------------------------- 跑用例
        log(f"执行接口用例（scope={args.scope}）")
        pytest_cmd = [
            PYTHON, "-m", "pytest", "-q",
            "--junitxml=reports/junit.xml",
            "--alluredir=reports/allure-results",
        ]
        if args.scope == "smoke":
            pytest_cmd += ["-m", "smoke"]
        pytest_rc = run(pytest_cmd, cwd=ROOT, env=env)

        # ---------------------------------------------------------- 出报告
        log("生成自制 HTML 报告")
        run([PYTHON, str(ROOT / "tools" / "report_html.py")], cwd=ROOT, env=env)

        log("生成通过率趋势页")
        run([PYTHON, str(ROOT / "tools" / "trend.py")], cwd=ROOT, env=env)

        allure_bin = find_allure()
        allure_report_dir = reports / "allure-report"
        allure_ok = False
        if allure_bin:
            log("生成 Allure 报告")
            rc = run(
                [str(allure_bin), "generate", "reports/allure-results",
                 "-o", "reports/allure-report", "--clean"],
                cwd=ROOT, env=env,
            )
            # 只认「目录里真的有 index.html」，不认退出码 —— allure.bat 出错也可能返回 0
            allure_ok = rc == 0 and (allure_report_dir / "index.html").exists()
            if not allure_ok:
                print(
                    "\n[警告] Allure 报告生成失败（自制 HTML 报告不受影响）。"
                    "常见原因：JAVA_HOME 未设置或指向无效目录。",
                    file=sys.stderr,
                )
        else:
            print("\n（未找到 Allure CLI，跳过 Allure 报告 —— 自制 HTML 报告不受影响）")

        # ---------------------------------------------------------- 汇总
        def show(path: Path, label: str, extra: str = "") -> None:
            mark = "OK " if path.exists() else "缺失"
            print(f"  [{mark}] {label}：{path}{extra}")

        print("\n" + "=" * 62)
        print(f"  用例结果：{'全部通过' if pytest_rc == 0 else '存在失败，详见报告'}")
        show(reports / "测试报告.html", "HTML 报告　")
        show(reports / "通过率趋势.html", "趋势页　　")
        show(allure_report_dir / "index.html", "Allure　　",
             "（用 allure open 或起静态服务器打开）" if allure_ok else "")
        print("=" * 62)
        return pytest_rc
    finally:
        if proc is not None:
            log("停止被测系统")
            proc.terminate()
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                proc.kill()


def find_allure() -> Path | None:
    """定位 Allure CLI：优先环境变量，其次工作区 .tools 下的解压目录。"""
    env_path = os.getenv("MES_ALLURE_BIN")
    if env_path and Path(env_path).exists():
        return Path(env_path)

    tools_dir = WORKSPACE / ".tools"
    if not tools_dir.exists():
        return None
    for d in sorted(tools_dir.glob("allure-*")):
        if not d.is_dir():
            continue
        for name in ("allure.bat", "allure"):
            candidate = d / "bin" / name
            if candidate.exists():
                return candidate
    return None


if __name__ == "__main__":
    sys.exit(main())

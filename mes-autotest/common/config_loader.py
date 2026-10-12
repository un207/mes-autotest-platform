"""配置与数据加载。

三类加载各自独立：
  - load_config()      环境配置（支持环境变量覆盖敏感项）
  - load_endpoints()   接口路径登记表
  - load_cases(name)   YAML 数据驱动用例数据
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"配置文件不存在: {path}")
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_config() -> dict[str, Any]:
    """加载环境配置，敏感项与地址支持环境变量覆盖。

    环境变量优先级高于 yml，便于 CI 与换机运行时不改仓库文件：
        MES_BASE_URL  MES_DB_HOST  MES_DB_PORT  MES_DB_USER  MES_DB_PASSWORD  MES_DB_NAME
    """
    cfg = _load_yaml(CONFIG_DIR / "env.yml")

    api = dict(cfg.get("api", {}))
    api["base_url"] = os.getenv("MES_BASE_URL", api.get("base_url", "http://127.0.0.1:8080"))
    api["timeout"] = int(os.getenv("MES_API_TIMEOUT", api.get("timeout", 10)))

    db = dict(cfg.get("db", {}))
    db["host"] = os.getenv("MES_DB_HOST", db.get("host", "127.0.0.1"))
    db["port"] = int(os.getenv("MES_DB_PORT", db.get("port", 3306)))
    db["user"] = os.getenv("MES_DB_USER", db.get("user", "root"))
    db["password"] = os.getenv("MES_DB_PASSWORD", db.get("password", ""))
    db["database"] = os.getenv("MES_DB_NAME", db.get("database", "mes_test"))
    db["charset"] = db.get("charset", "utf8mb4")
    db["connect_timeout"] = int(db.get("connect_timeout", 5))

    run = dict(cfg.get("run", {}))
    run["data_prefix"] = os.getenv("MES_TEST_PREFIX", run.get("data_prefix", "M2"))
    run["cleanup"] = str(os.getenv("MES_TEST_CLEANUP", run.get("cleanup", True))).lower() not in ("false", "0", "no")

    return {"api": api, "db": db, "run": run}


class Endpoints:
    """接口路径登记表，支持占位符填充。"""

    def __init__(self, table: dict[str, str] | None = None) -> None:
        self._table = table if table is not None else _load_yaml(CONFIG_DIR / "endpoints.yml")

    def path(self, key: str, **params: Any) -> str:
        raw = self._table.get(key)
        if raw is None:
            raise KeyError(f"endpoints.yml 中未登记该接口: {key}")
        return raw.format(**params) if params else raw

    def keys(self) -> list[str]:
        return sorted(self._table.keys())


def load_endpoints() -> Endpoints:
    return Endpoints()


def load_cases(name: str) -> Any:
    """加载 data/ 下的用例数据文件，name 可带或不带 .yml 后缀。"""
    filename = name if name.endswith((".yml", ".yaml")) else f"{name}.yml"
    return _load_yaml(DATA_DIR / filename)

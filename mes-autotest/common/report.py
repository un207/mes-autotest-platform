"""报告适配层 —— Allure 为软依赖。

为什么做这层：Allure 报告是 M3 的目标，但 M2 阶段（以及任何没装 allure-pytest 的机器上）
框架必须照样能跑。这里把 allure 的调用收在一处，装了就出富报告，没装就静默降级为普通 pytest。
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from functools import wraps
from typing import Any, Callable, Iterator

try:  # pragma: no cover - 取决于运行环境
    import allure

    HAS_ALLURE = True
except ImportError:  # pragma: no cover
    allure = None
    HAS_ALLURE = False


@contextmanager
def step(title: str) -> Iterator[None]:
    """把一段操作标记为报告中的一个步骤。未装 allure 时为空操作。"""
    if HAS_ALLURE:
        with allure.step(title):
            yield
    else:
        yield


def attach_json(name: str, payload: Any) -> None:
    """把请求/响应体作为附件挂到报告上，便于回溯失败现场。"""
    if not HAS_ALLURE:
        return
    try:
        content = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
    except (TypeError, ValueError):
        content = str(payload)
    allure.attach(content, name=name, attachment_type=allure.attachment_type.JSON)


def attach_text(name: str, content: str) -> None:
    if not HAS_ALLURE:
        return
    allure.attach(content, name=name, attachment_type=allure.attachment_type.TEXT)


def title(text: str) -> Callable:
    def deco(func: Callable) -> Callable:
        if HAS_ALLURE:
            return allure.title(text)(func)
        return func

    return deco


def feature(name: str) -> Callable:
    def deco(func: Callable) -> Callable:
        if HAS_ALLURE:
            return allure.feature(name)(func)
        return func

    return deco


def severity(level: str) -> Callable:
    """level: blocker / critical / normal / minor / trivial"""

    def deco(func: Callable) -> Callable:
        if HAS_ALLURE and hasattr(allure, "severity_level"):
            try:
                return allure.severity(allure.severity_level(level.upper()))(func)
            except (KeyError, ValueError):
                return func
        return func

    return deco


def attach_case_data(func: Callable) -> Callable:
    """把用例参数以附件形式写入报告，让数据驱动用例的每一条参数都可见。"""

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        if HAS_ALLURE:
            try:
                payload = {"args": [a for a in args if isinstance(a, (str, int, float, bool, dict, list))],
                           "kwargs": kwargs}
                attach_json("用例参数", payload)
            except Exception:  # noqa: BLE001 - 附件失败绝不影响用例执行
                pass
        return func(*args, **kwargs)

    return wrapper

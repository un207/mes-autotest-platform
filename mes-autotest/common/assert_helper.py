"""断言助手。

统一把「失败原因 + 完整响应上下文」拼进断言消息。用例失败时不用再去翻日志 ——
traceId、HTTP 状态、业务码、响应体都在消息里。
"""

from __future__ import annotations

from typing import Any, Iterable

from common.http_client import ApiResult


def assert_http_status(res: ApiResult, expected: int, hint: str = "") -> ApiResult:
    assert res.http_status == expected, (
        f"{_tag(hint)}期望 HTTP {expected}，实际 {res.http_status}\n  {res.describe()}"
    )
    return res


def assert_ok(res: ApiResult, hint: str = "") -> Any:
    """断言业务成功（HTTP 200 且 code == 0），返回 data。"""
    assert res.http_status == 200, (
        f"{_tag(hint)}期望 HTTP 200，实际 {res.http_status}\n  {res.describe()}"
    )
    assert res.code == 0, (
        f"{_tag(hint)}期望业务成功(code=0)，实际 code={res.code} message={res.message!r}\n  {res.describe()}"
    )
    return res.data


def assert_business_code(res: ApiResult, expected_code: int, hint: str = "") -> ApiResult:
    """断言业务码。负向用例用它——被业务规则拒绝时 HTTP 仍是 200，只有 code 变化。"""
    assert res.code == expected_code, (
        f"{_tag(hint)}期望业务码 {expected_code}，实际 {res.code} message={res.message!r}\n  {res.describe()}"
    )
    return res


def assert_rejected(res: ApiResult, expected_code: int, hint: str = "") -> ApiResult:
    """断言请求被业务规则正确拒绝：HTTP 200 + 指定业务码（非 0）。"""
    assert res.http_status == 200, (
        f"{_tag(hint)}被拒绝的请求也应返回 HTTP 200，实际 {res.http_status}\n  {res.describe()}"
    )
    assert res.code == expected_code, (
        f"{_tag(hint)}期望被拒绝(code={expected_code})，实际 code={res.code} message={res.message!r}\n  {res.describe()}"
    )
    assert res.code != 0, f"{_tag(hint)}期望失败却被判定成功\n  {res.describe()}"
    return res


def assert_not_found_route(res: ApiResult, hint: str = "") -> ApiResult:
    """断言访问了不存在的路由：HTTP 404 + 同构 body。"""
    assert res.http_status == 404, (
        f"{_tag(hint)}未匹配路由应返回 HTTP 404，实际 {res.http_status}\n  {res.describe()}"
    )
    assert res.code == 40400, (
        f"{_tag(hint)}未匹配路由应返回 code=40400，实际 {res.code}\n  {res.describe()}"
    )
    return res


def assert_fields(data: Any, **expected: Any) -> None:
    """断言 data 中的若干字段等于期望值。"""
    assert isinstance(data, dict), f"期望 data 是对象，实际 {type(data).__name__}: {data!r}"
    for key, want in expected.items():
        got = data.get(key)
        assert got == want, f"字段 {key} 不符：期望 {want!r}，实际 {got!r}\n  完整 data={data}"


def assert_keys(data: Any, keys: Iterable[str], hint: str = "") -> None:
    """断言响应对象包含指定字段（字段恒存在，值可为 null）。"""
    assert isinstance(data, dict), (
        f"{_tag(hint)}期望 data 是对象，实际 {type(data).__name__}: {data!r}"
    )
    missing = [k for k in keys if k not in data]
    assert not missing, f"{_tag(hint)}data 缺少字段 {missing}，实际字段={sorted(data.keys())}"


def assert_list(data: Any, hint: str = "") -> list:
    assert isinstance(data, list), (
        f"{_tag(hint)}期望 data 是列表，实际 {type(data).__name__}: {str(data)[:200]}"
    )
    return data


def assert_true(condition: bool, message: str) -> None:
    assert condition, message


def assert_all_ok(results: list[ApiResult], hint: str = "") -> None:
    """批量断言多个请求全部成功（用于构造前置数据的链路）。"""
    for idx, res in enumerate(results):
        assert res.ok, f"{_tag(hint)}第 {idx + 1} 个前置请求未成功\n  {res.describe()}"


def _tag(hint: str) -> str:
    return f"[{hint}] " if hint else ""

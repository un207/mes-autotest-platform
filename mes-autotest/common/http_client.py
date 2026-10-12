"""HTTP 客户端封装。

设计要点：
  1. 统一响应模型 —— MES 所有接口都返回同构 body，这里一次性解析成 ApiResult，
     用例里不再到处写 resp.json()["data"]。
  2. 失败信息自带 traceId —— MES 每个响应都带 traceId，把它放进断言失败信息里，
     排查时可直接去服务日志搜这一段，这是接口自动化最实用的抓手。
  3. 不做隐式断言 —— 客户端只负责发请求与解析，判定交给 assert_helper，
     避免「工具层偷偷吞掉失败」。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import requests


@dataclass
class ApiResult:
    """一次接口调用的完整结果。"""

    method: str
    url: str
    http_status: int
    raw_text: str
    elapsed_ms: float
    code: int | None = None
    message: str | None = None
    data: Any = None
    trace_id: str | None = None
    json_error: str | None = None

    @property
    def ok(self) -> bool:
        """业务成功：HTTP 200 且业务码为 0。"""
        return self.http_status == 200 and self.code == 0

    @property
    def business_failed(self) -> bool:
        """被业务规则挡住了（HTTP 200 但 code != 0）。负向用例断言的就是这一支。"""
        return self.http_status == 200 and self.code not in (0, None)

    def describe(self, max_body: int = 300) -> str:
        """生成便于排查的失败描述，含 traceId 与截断的响应体。"""
        body = self.raw_text if len(self.raw_text) <= max_body else self.raw_text[:max_body] + "…"
        parts = [
            f"{self.method} {self.url}",
            f"HTTP={self.http_status} code={self.code} message={self.message!r}",
            f"traceId={self.trace_id or '-'}",
            f"耗时={self.elapsed_ms:.0f}ms",
            f"body={body}",
        ]
        if self.json_error:
            parts.append(f"JSON解析失败={self.json_error}")
        return " | ".join(parts)

    def data_keys(self) -> list[str]:
        return list(self.data.keys()) if isinstance(self.data, dict) else []

    def __repr__(self) -> str:  # pragma: no cover - 仅调试用
        return f"<ApiResult {self.method} {self.url} http={self.http_status} code={self.code}>"


@dataclass
class ApiClient:
    """基于 requests.Session 的轻量客户端，复用连接、统一 base_url 与超时。"""

    base_url: str
    timeout: int = 10
    verbose: bool = False
    session: requests.Session = field(default_factory=requests.Session)

    def __post_init__(self) -> None:
        self.base_url = self.base_url.rstrip("/")
        self.session.headers.update({"Content-Type": "application/json; charset=UTF-8"})

    # ------------------------------------------------------------------ 基础调用

    def call(
        self,
        method: str,
        path: str,
        *,
        json_body: Any = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: int | None = None,
    ) -> ApiResult:
        """发起一次请求并解析统一响应体。任何 HTTP 状态码都不抛异常，交由断言层判定。"""
        url = path if path.startswith("http") else f"{self.base_url}{path}"
        started = time.perf_counter()
        try:
            resp = self.session.request(
                method=method.upper(),
                url=url,
                json=json_body,
                params=params,
                headers=headers,
                timeout=timeout or self.timeout,
            )
        except requests.RequestException as exc:
            # 连不上服务属于环境问题，单独给出可操作的提示，避免看起来像用例失败
            raise AssertionError(
                f"请求发送失败：{method.upper()} {url} —— {exc.__class__.__name__}: {exc}\n"
                f"提示：确认 MES 服务已启动（mvn spring-boot:run），且 base_url={self.base_url} 可访问。"
            ) from exc

        elapsed_ms = (time.perf_counter() - started) * 1000
        result = ApiResult(
            method=method.upper(),
            url=url,
            http_status=resp.status_code,
            raw_text=resp.text,
            elapsed_ms=elapsed_ms,
            trace_id=resp.headers.get("X-Request-Id"),
        )

        try:
            payload = resp.json()
        except ValueError as exc:
            result.json_error = str(exc)
        else:
            if isinstance(payload, dict):
                result.code = payload.get("code")
                result.message = payload.get("message")
                result.data = payload.get("data")
                result.trace_id = payload.get("traceId") or result.trace_id
            else:
                result.json_error = f"响应体不是 JSON 对象，实际类型 {type(payload).__name__}"

        if self.verbose:
            print(f"[API] {result.describe()}")

        return result

    def get(self, path: str, **kwargs: Any) -> ApiResult:
        return self.call("GET", path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> ApiResult:
        return self.call("POST", path, **kwargs)

    def put(self, path: str, **kwargs: Any) -> ApiResult:
        return self.call("PUT", path, **kwargs)

    def delete(self, path: str, **kwargs: Any) -> ApiResult:
        return self.call("DELETE", path, **kwargs)

    # ------------------------------------------------------------------ 便捷封装

    def is_reachable(self) -> bool:
        """服务是否可达（用于 session 级前置检查，失败时给出明确提示）。"""
        try:
            return self.get("/api/health", timeout=3).http_status == 200
        except AssertionError:
            return False

    def close(self) -> None:
        self.session.close()

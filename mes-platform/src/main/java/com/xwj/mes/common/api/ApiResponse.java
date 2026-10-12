package com.xwj.mes.common.api;

import org.slf4j.MDC;

/**
 * 统一响应体。所有接口（含异常）都返回该结构，测试脚本只需一套断言模板。
 *
 * <pre>
 * { "code": 0, "message": "成功", "data": {...}, "traceId": "...", "timestamp": 1728648000000 }
 * </pre>
 */
public class ApiResponse<T> {

    private int code;
    private String message;
    private T data;
    private String traceId;
    private long timestamp;

    public ApiResponse() {
        this.timestamp = System.currentTimeMillis();
    }

    public static <T> ApiResponse<T> ok(T data) {
        ApiResponse<T> r = new ApiResponse<>();
        r.code = ErrorCode.SUCCESS.getCode();
        r.message = ErrorCode.SUCCESS.getMessage();
        r.data = data;
        r.traceId = currentTraceId();
        return r;
    }

    public static ApiResponse<Void> ok() {
        return ok(null);
    }

    public static <T> ApiResponse<T> fail(ErrorCode errorCode) {
        return fail(errorCode.getCode(), errorCode.getMessage());
    }

    public static <T> ApiResponse<T> fail(ErrorCode errorCode, String message) {
        return fail(errorCode.getCode(), message);
    }

    public static <T> ApiResponse<T> fail(int code, String message) {
        ApiResponse<T> r = new ApiResponse<>();
        r.code = code;
        r.message = message;
        r.traceId = currentTraceId();
        return r;
    }

    private static String currentTraceId() {
        return MDC.get("traceId");
    }

    public int getCode() {
        return code;
    }

    public void setCode(int code) {
        this.code = code;
    }

    public String getMessage() {
        return message;
    }

    public void setMessage(String message) {
        this.message = message;
    }

    public T getData() {
        return data;
    }

    public void setData(T data) {
        this.data = data;
    }

    public String getTraceId() {
        return traceId;
    }

    public void setTraceId(String traceId) {
        this.traceId = traceId;
    }

    public long getTimestamp() {
        return timestamp;
    }

    public void setTimestamp(long timestamp) {
        this.timestamp = timestamp;
    }
}

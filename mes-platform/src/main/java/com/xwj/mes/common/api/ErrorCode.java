package com.xwj.mes.common.api;

/**
 * 业务状态码。前 3 位对齐 HTTP 语义，后 2 位用于细分，便于脚本断言时精确匹配。
 */
public enum ErrorCode {

    SUCCESS(0, "成功"),

    PARAM_INVALID(40000, "参数校验失败"),
    JSON_PARSE_ERROR(40001, "请求体格式错误"),

    NOT_FOUND(40400, "资源不存在"),

    STATE_CONFLICT(40900, "业务状态冲突"),
    DATA_DUPLICATED(40901, "数据已存在"),

    INTERNAL_ERROR(50000, "系统内部错误"),
    DB_ERROR(50001, "数据库访问异常"),

    SERVICE_UNAVAILABLE(50300, "服务依赖不可用");

    private final int code;
    private final String message;

    ErrorCode(int code, String message) {
        this.code = code;
        this.message = message;
    }

    public int getCode() {
        return code;
    }

    public String getMessage() {
        return message;
    }
}

package com.xwj.mes.common.exception;

import com.xwj.mes.common.api.ErrorCode;

/**
 * 业务异常。仅用于「可预期的业务失败」，系统级异常交给 GlobalExceptionHandler 兜底。
 */
public class BizException extends RuntimeException {

    private final int code;

    public BizException(ErrorCode errorCode) {
        super(errorCode.getMessage());
        this.code = errorCode.getCode();
    }

    public BizException(ErrorCode errorCode, String message) {
        super(message);
        this.code = errorCode.getCode();
    }

    public int getCode() {
        return code;
    }

    public static BizException notFound(String message) {
        return new BizException(ErrorCode.NOT_FOUND, message);
    }

    public static BizException stateConflict(String message) {
        return new BizException(ErrorCode.STATE_CONFLICT, message);
    }

    public static BizException duplicated(String message) {
        return new BizException(ErrorCode.DATA_DUPLICATED, message);
    }
}

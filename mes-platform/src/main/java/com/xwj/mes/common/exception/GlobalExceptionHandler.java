package com.xwj.mes.common.exception;

import com.xwj.mes.common.api.ApiResponse;
import com.xwj.mes.common.api.ErrorCode;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.ConstraintViolation;
import jakarta.validation.ConstraintViolationException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.validation.BindException;
import org.springframework.validation.FieldError;
import org.springframework.web.HttpRequestMethodNotSupportedException;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.MissingServletRequestParameterException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;
import org.springframework.web.servlet.NoHandlerFoundException;
import org.springframework.web.servlet.resource.NoResourceFoundException;

import java.util.stream.Collectors;

/**
 * 全局异常处理器。
 *
 * <p>响应契约（测试脚本按此写断言模板即可）：</p>
 * <ul>
 *   <li><b>HTTP 200</b> —— 请求已到达 Controller 且属于「业务结果」范畴，包括参数校验失败、
 *       业务状态冲突、资源在业务上不存在。结果一律由 {@code body.code} 承载，脚本只需断言 code。</li>
 *   <li><b>HTTP 404</b> —— 路由或静态资源不存在（请求压根没匹配上任何接口），属基础设施层失败。</li>
 *   <li><b>HTTP 500</b> —— 未预期异常，属代码缺陷，需携 traceId 查日志。</li>
 * </ul>
 * <p>三种情况返回的 body 结构完全一致，脚本不需要分叉解析。</p>
 */
@RestControllerAdvice
public class GlobalExceptionHandler {

    private static final Logger log = LoggerFactory.getLogger(GlobalExceptionHandler.class);

    @ExceptionHandler(BizException.class)
    public ApiResponse<Void> handleBiz(BizException e, HttpServletRequest request) {
        log.warn("业务异常 uri={} code={} msg={}", request.getRequestURI(), e.getCode(), e.getMessage());
        return ApiResponse.fail(e.getCode(), e.getMessage());
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ApiResponse<Void> handleMethodArgumentNotValid(MethodArgumentNotValidException e) {
        String detail = e.getBindingResult().getFieldErrors().stream()
                .map(f -> f.getField() + ": " + f.getDefaultMessage())
                .collect(Collectors.joining("; "));
        return ApiResponse.fail(ErrorCode.PARAM_INVALID, detail);
    }

    @ExceptionHandler(BindException.class)
    public ApiResponse<Void> handleBind(BindException e) {
        String detail = e.getBindingResult().getFieldErrors().stream()
                .map(FieldError::getDefaultMessage)
                .collect(Collectors.joining("; "));
        return ApiResponse.fail(ErrorCode.PARAM_INVALID, detail);
    }

    @ExceptionHandler(ConstraintViolationException.class)
    public ApiResponse<Void> handleConstraintViolation(ConstraintViolationException e) {
        String detail = e.getConstraintViolations().stream()
                .map(ConstraintViolation::getMessage)
                .collect(Collectors.joining("; "));
        return ApiResponse.fail(ErrorCode.PARAM_INVALID, detail);
    }

    @ExceptionHandler(MissingServletRequestParameterException.class)
    public ApiResponse<Void> handleMissingParam(MissingServletRequestParameterException e) {
        return ApiResponse.fail(ErrorCode.PARAM_INVALID, "缺少必填参数: " + e.getParameterName());
    }

    @ExceptionHandler(MethodArgumentTypeMismatchException.class)
    public ApiResponse<Void> handleTypeMismatch(MethodArgumentTypeMismatchException e) {
        return ApiResponse.fail(ErrorCode.PARAM_INVALID, "参数类型不匹配: " + e.getName());
    }

    @ExceptionHandler(HttpMessageNotReadableException.class)
    public ApiResponse<Void> handleNotReadable(HttpMessageNotReadableException e) {
        log.warn("请求体解析失败: {}", e.getMessage());
        return ApiResponse.fail(ErrorCode.JSON_PARSE_ERROR, "请求体不是合法 JSON 或字段类型错误");
    }

    @ExceptionHandler(DuplicateKeyException.class)
    public ApiResponse<Void> handleDuplicateKey(DuplicateKeyException e) {
        log.warn("唯一键冲突: {}", e.getMessage());
        return ApiResponse.fail(ErrorCode.DATA_DUPLICATED, "数据已存在，违反唯一约束");
    }

    @ExceptionHandler(NoHandlerFoundException.class)
    public ResponseEntity<ApiResponse<Void>> handleNoHandler(NoHandlerFoundException e) {
        return ResponseEntity.status(HttpStatus.NOT_FOUND)
                .body(ApiResponse.fail(ErrorCode.NOT_FOUND, "接口不存在: " + e.getRequestURL()));
    }

    /**
     * Spring 6.1 起，未匹配到任何 handler 的请求由静态资源处理器抛出该异常。
     * 若不显式接管，会被下面的兜底分支吞成 50000，掩盖「路径写错」这一脚本侧最常见故障。
     */
    @ExceptionHandler(NoResourceFoundException.class)
    public ResponseEntity<ApiResponse<Void>> handleNoResource(NoResourceFoundException e) {
        return ResponseEntity.status(HttpStatus.NOT_FOUND)
                .body(ApiResponse.fail(ErrorCode.NOT_FOUND, "接口或资源不存在: /" + e.getResourcePath()));
    }

    @ExceptionHandler(HttpRequestMethodNotSupportedException.class)
    public ApiResponse<Void> handleMethodNotSupported(HttpRequestMethodNotSupportedException e) {
        return ApiResponse.fail(ErrorCode.PARAM_INVALID, "请求方法不支持: " + e.getMethod());
    }

    @ExceptionHandler(Exception.class)
    public ApiResponse<Void> handleUnknown(Exception e, HttpServletRequest request) {
        log.error("未预期异常 uri={}", request.getRequestURI(), e);
        return ApiResponse.fail(ErrorCode.INTERNAL_ERROR, "系统内部错误，请携 traceId 排查日志");
    }
}

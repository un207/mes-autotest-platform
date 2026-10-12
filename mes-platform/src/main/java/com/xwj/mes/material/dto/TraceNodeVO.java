package com.xwj.mes.material.dto;

import com.fasterxml.jackson.annotation.JsonFormat;
import com.xwj.mes.material.TraceNodeType;
import com.xwj.mes.material.TraceRecord;

import java.time.LocalDateTime;

/**
 * 追溯节点视图。
 */
public record TraceNodeVO(
        TraceNodeType nodeType,
        String nodeLabel,
        String nodeDesc,
        String operator,
        String orderNo,
        @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss") LocalDateTime traceTime
) {

    public static TraceNodeVO from(TraceRecord record) {
        return new TraceNodeVO(
                record.getNodeType(),
                record.getNodeType() == null ? null : record.getNodeType().getLabel(),
                record.getNodeDesc(),
                record.getOperator(),
                record.getOrderNo(),
                record.getTraceTime());
    }
}

package com.xwj.mes.material.dto;

import com.xwj.mes.material.MaterialBatch;

import java.util.List;

/**
 * 正向追溯结果：给定批次，反查它流向了哪个工单、经历哪些节点。
 */
public record BatchTraceVO(
        MaterialBatch batch,
        String boundOrderNo,
        List<TraceNodeVO> nodes
) {
}

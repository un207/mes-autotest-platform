package com.xwj.mes.material.dto;

import com.xwj.mes.material.MaterialBatch;
import com.xwj.mes.quality.QualityInspection;
import com.xwj.mes.workorder.dto.WorkOrderVO;

import java.util.List;

/**
 * 反向追溯结果：给定工单，列出用到的全部批次与它们的节点流水、以及该工单的不良明细。
 */
public record OrderTraceVO(
        WorkOrderVO order,
        List<MaterialBatch> batches,
        List<TraceNodeVO> nodes,
        List<QualityInspection> defects
) {
}

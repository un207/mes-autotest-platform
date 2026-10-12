package com.xwj.mes.stats.dto;

import lombok.Getter;
import lombok.Setter;

import java.math.BigDecimal;

/**
 * 平台级总览指标。M3 阶段「通过率趋势」页面与用例断言都以此为数据源。
 */
@Getter
@Setter
public class OverviewVO {

    private Integer totalOrders;
    private Integer openOrders;
    private Integer closedOrders;
    private Integer totalPlanQty;
    private Integer totalFinishedQty;
    private Integer totalQualifiedQty;
    private Integer totalDefectiveQty;
    private BigDecimal yieldRate;
    private Integer inspectionCount;
    private Integer inspectionFailCount;
    private Integer batchCount;
    private Integer deviceDataCount;
    private Integer deviceAbnormalCount;
}

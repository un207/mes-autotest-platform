package com.xwj.mes.stats.dto;

import lombok.Getter;
import lombok.Setter;

import java.math.BigDecimal;

/**
 * 生产日报统计行（按日期 × 产线）。
 */
@Getter
@Setter
public class ProductionStatVO {

    private String statDate;
    private String lineCode;
    private Integer orderCount;
    private Integer planQty;
    private Integer finishedQty;
    private Integer qualifiedQty;
    private Integer defectiveQty;
    private BigDecimal yieldRate;
}

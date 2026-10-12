package com.xwj.mes.stats.dto;

import lombok.Getter;
import lombok.Setter;

import java.math.BigDecimal;

/**
 * 单工单良率统计行。
 */
@Getter
@Setter
public class OrderYieldVO {

    private String orderNo;
    private String productCode;
    private Integer planQty;
    private Integer finishedQty;
    private Integer qualifiedQty;
    private Integer defectiveQty;
    private BigDecimal yieldRate;
}

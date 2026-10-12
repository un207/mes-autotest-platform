package com.xwj.mes.workorder.dto;

import com.fasterxml.jackson.annotation.JsonFormat;
import com.fasterxml.jackson.annotation.JsonInclude;
import com.xwj.mes.workorder.OrderStatus;
import com.xwj.mes.workorder.WorkOrder;
import com.xwj.mes.workorder.WorkReport;
import lombok.Getter;
import lombok.Setter;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDateTime;
import java.util.List;

/**
 * 工单视图对象。对外稳定契约，不直接暴露实体（实体带逻辑删除位等持久层细节）。
 */
@Getter
@Setter
@JsonInclude(JsonInclude.Include.NON_NULL)
public class WorkOrderVO {

    private Long id;
    private String orderNo;
    private String productCode;
    private String productName;
    private Integer planQty;
    private Integer finishedQty;
    private Integer qualifiedQty;
    private Integer defectiveQty;
    private OrderStatus status;
    private String statusLabel;
    private String lineCode;
    private String workshop;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime planStartTime;
    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime planEndTime;
    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime actualStartTime;
    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime actualEndTime;
    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime createTime;
    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime updateTime;

    private String remark;

    /** 完工进度（%），已报工 / 计划 */
    private BigDecimal progressRate;

    /** 直通率（%），合格 / 已报工 */
    private BigDecimal yieldRate;

    /** 报工明细，仅详情接口返回 */
    private List<WorkReport> reports;

    public static WorkOrderVO from(WorkOrder order) {
        WorkOrderVO vo = new WorkOrderVO();
        vo.id = order.getId();
        vo.orderNo = order.getOrderNo();
        vo.productCode = order.getProductCode();
        vo.productName = order.getProductName();
        vo.planQty = order.getPlanQty();
        vo.finishedQty = order.getFinishedQty();
        vo.qualifiedQty = order.getQualifiedQty();
        vo.defectiveQty = order.getDefectiveQty();
        vo.status = order.getStatus();
        vo.statusLabel = order.getStatus() == null ? null : order.getStatus().getLabel();
        vo.lineCode = order.getLineCode();
        vo.workshop = order.getWorkshop();
        vo.planStartTime = order.getPlanStartTime();
        vo.planEndTime = order.getPlanEndTime();
        vo.actualStartTime = order.getActualStartTime();
        vo.actualEndTime = order.getActualEndTime();
        vo.createTime = order.getCreateTime();
        vo.updateTime = order.getUpdateTime();
        vo.remark = order.getRemark();
        vo.progressRate = rate(order.getFinishedQty(), order.getPlanQty());
        vo.yieldRate = rate(order.getQualifiedQty(), order.getFinishedQty());
        return vo;
    }

    private static BigDecimal rate(Integer numerator, Integer denominator) {
        if (numerator == null || denominator == null || denominator == 0) {
            return BigDecimal.ZERO.setScale(2, RoundingMode.HALF_UP);
        }
        return BigDecimal.valueOf(numerator)
                .multiply(BigDecimal.valueOf(100))
                .divide(BigDecimal.valueOf(denominator), 2, RoundingMode.HALF_UP);
    }
}

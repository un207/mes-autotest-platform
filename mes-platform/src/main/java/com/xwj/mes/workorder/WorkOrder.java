package com.xwj.mes.workorder;

import com.baomidou.mybatisplus.annotation.TableName;
import com.fasterxml.jackson.annotation.JsonFormat;
import com.xwj.mes.common.entity.BaseEntity;
import lombok.Getter;
import lombok.Setter;

import java.time.LocalDateTime;

/**
 * 生产工单。MES 的主线单据：创建 → 派工 → 报工 → 关闭。
 */
@Getter
@Setter
@TableName("mes_work_order")
public class WorkOrder extends BaseEntity {

    private static final long serialVersionUID = 1L;

    /** 工单号，业务唯一键 */
    private String orderNo;

    private String productCode;

    private String productName;

    /** 计划数量 */
    private Integer planQty;

    /** 累计报工数量 */
    private Integer finishedQty;

    /** 累计合格数量 */
    private Integer qualifiedQty;

    /** 累计不良数量 */
    private Integer defectiveQty;

    private OrderStatus status;

    /** 产线编号 */
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

    private String remark;
}

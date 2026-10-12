package com.xwj.mes.quality;

import com.baomidou.mybatisplus.annotation.TableName;
import com.fasterxml.jackson.annotation.JsonFormat;
import com.xwj.mes.common.entity.BaseEntity;
import lombok.Getter;
import lombok.Setter;

import java.time.LocalDateTime;

/**
 * 质检记录。支持按工单、批次、不良代码三个维度追溯。
 */
@Getter
@Setter
@TableName("mes_quality_inspection")
public class QualityInspection extends BaseEntity {

    private static final long serialVersionUID = 1L;

    /** 质检单号 */
    private String inspectNo;

    private String orderNo;

    /** 关联物料批次（来料/出货检验时必填） */
    private String batchNo;

    private InspectType inspectType;

    private Integer inspectQty;

    private Integer qualifiedQty;

    private Integer defectiveQty;

    /** 不良代码，不良数大于 0 时必填 */
    private String defectCode;

    private InspectResult result;

    /** 质检员 */
    private String inspector;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime inspectTime;

    private String remark;
}

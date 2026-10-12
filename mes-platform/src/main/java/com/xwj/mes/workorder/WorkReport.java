package com.xwj.mes.workorder;

import com.baomidou.mybatisplus.annotation.TableName;
import com.fasterxml.jackson.annotation.JsonFormat;
import com.xwj.mes.common.entity.BaseEntity;
import lombok.Getter;
import lombok.Setter;

import java.time.LocalDateTime;

/**
 * 报工记录。一个工单可有多条，工单上的累计数量由此表汇总而来。
 */
@Getter
@Setter
@TableName("mes_work_report")
public class WorkReport extends BaseEntity {

    private static final long serialVersionUID = 1L;

    private String reportNo;

    private String orderNo;

    /** 本次报工数量 */
    private Integer reportQty;

    /** 本次合格数 */
    private Integer qualifiedQty;

    /** 本次不良数 */
    private Integer defectiveQty;

    /** 报工人（工号或姓名） */
    private String worker;

    /** 报工设备编号，用于回连数采数据 */
    private String equipmentCode;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime reportTime;

    private String remark;
}

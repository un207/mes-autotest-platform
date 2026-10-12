package com.xwj.mes.material;

import com.baomidou.mybatisplus.annotation.TableName;
import com.fasterxml.jackson.annotation.JsonFormat;
import com.xwj.mes.common.entity.BaseEntity;
import lombok.Getter;
import lombok.Setter;

import java.time.LocalDateTime;

/**
 * 物料批次。批次是追溯的最小单位，正反向追溯都以它为主线。
 */
@Getter
@Setter
@TableName("mes_material_batch")
public class MaterialBatch extends BaseEntity {

    private static final long serialVersionUID = 1L;

    /** 批次号，业务唯一键 */
    private String batchNo;

    private String materialCode;

    private String materialName;

    /** 绑定的工单号，未领用时为空 */
    private String orderNo;

    private String supplier;

    private Integer qty;

    private String unit;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime inboundTime;

    private BatchStatus status;

    private String remark;
}

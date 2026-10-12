package com.xwj.mes.device;

import com.baomidou.mybatisplus.annotation.TableName;
import com.fasterxml.jackson.annotation.JsonFormat;
import com.xwj.mes.common.entity.BaseEntity;
import lombok.Getter;
import lombok.Setter;

import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * 设备数采记录。既保留原始上报串，也保留解析后的数值，便于异常注入场景的比对断言。
 */
@Getter
@Setter
@TableName("mes_device_data")
public class DeviceData extends BaseEntity {

    private static final long serialVersionUID = 1L;

    private String equipmentCode;

    private String lineCode;

    private MetricType metric;

    /** 解析后的数值，解析失败时为空 */
    private BigDecimal metricValue;

    /** 原始上报值，不丢失现场信息 */
    private String rawValue;

    private String unit;

    private QualityFlag qualityFlag;

    /** 异常/可疑原因，正常时为空 */
    private String qualityMessage;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime collectTime;
}

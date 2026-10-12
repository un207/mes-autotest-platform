package com.xwj.mes.device.dto;

import com.xwj.mes.common.api.PageQuery;
import com.xwj.mes.device.MetricType;
import com.xwj.mes.device.QualityFlag;

/**
 * 设备数采分页查询条件。
 */
public class DeviceDataQuery extends PageQuery {

    private String equipmentCode;

    private String lineCode;

    private MetricType metric;

    private QualityFlag qualityFlag;

    public String getEquipmentCode() {
        return equipmentCode;
    }

    public void setEquipmentCode(String equipmentCode) {
        this.equipmentCode = equipmentCode;
    }

    public String getLineCode() {
        return lineCode;
    }

    public void setLineCode(String lineCode) {
        this.lineCode = lineCode;
    }

    public MetricType getMetric() {
        return metric;
    }

    public void setMetric(MetricType metric) {
        this.metric = metric;
    }

    public QualityFlag getQualityFlag() {
        return qualityFlag;
    }

    public void setQualityFlag(QualityFlag qualityFlag) {
        this.qualityFlag = qualityFlag;
    }
}

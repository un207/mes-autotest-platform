package com.xwj.mes.quality.dto;

import com.xwj.mes.common.api.PageQuery;
import com.xwj.mes.quality.InspectResult;
import com.xwj.mes.quality.InspectType;

/**
 * 质检分页查询条件。
 */
public class QualityInspectionQuery extends PageQuery {

    private String orderNo;

    private String batchNo;

    private InspectType inspectType;

    private InspectResult result;

    private String defectCode;

    public String getOrderNo() {
        return orderNo;
    }

    public void setOrderNo(String orderNo) {
        this.orderNo = orderNo;
    }

    public String getBatchNo() {
        return batchNo;
    }

    public void setBatchNo(String batchNo) {
        this.batchNo = batchNo;
    }

    public InspectType getInspectType() {
        return inspectType;
    }

    public void setInspectType(InspectType inspectType) {
        this.inspectType = inspectType;
    }

    public InspectResult getResult() {
        return result;
    }

    public void setResult(InspectResult result) {
        this.result = result;
    }

    public String getDefectCode() {
        return defectCode;
    }

    public void setDefectCode(String defectCode) {
        this.defectCode = defectCode;
    }
}

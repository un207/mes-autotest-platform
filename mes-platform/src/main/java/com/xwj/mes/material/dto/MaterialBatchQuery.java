package com.xwj.mes.material.dto;

import com.xwj.mes.common.api.PageQuery;
import com.xwj.mes.material.BatchStatus;

/**
 * 物料批次分页查询条件。
 */
public class MaterialBatchQuery extends PageQuery {

    private String materialCode;

    private String orderNo;

    private BatchStatus status;

    /** 模糊匹配批次号或物料名称 */
    private String keyword;

    public String getMaterialCode() {
        return materialCode;
    }

    public void setMaterialCode(String materialCode) {
        this.materialCode = materialCode;
    }

    public String getOrderNo() {
        return orderNo;
    }

    public void setOrderNo(String orderNo) {
        this.orderNo = orderNo;
    }

    public BatchStatus getStatus() {
        return status;
    }

    public void setStatus(BatchStatus status) {
        this.status = status;
    }

    public String getKeyword() {
        return keyword;
    }

    public void setKeyword(String keyword) {
        this.keyword = keyword;
    }
}

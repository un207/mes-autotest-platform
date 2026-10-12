package com.xwj.mes.workorder.dto;

import com.xwj.mes.common.api.PageQuery;
import com.xwj.mes.workorder.OrderStatus;

/**
 * 工单分页查询条件。字段均可空，为空即不过滤。
 */
public class WorkOrderQuery extends PageQuery {

    private OrderStatus status;

    private String lineCode;

    private String productCode;

    /** 模糊匹配工单号或产品名称 */
    private String keyword;

    public OrderStatus getStatus() {
        return status;
    }

    public void setStatus(OrderStatus status) {
        this.status = status;
    }

    public String getLineCode() {
        return lineCode;
    }

    public void setLineCode(String lineCode) {
        this.lineCode = lineCode;
    }

    public String getProductCode() {
        return productCode;
    }

    public void setProductCode(String productCode) {
        this.productCode = productCode;
    }

    public String getKeyword() {
        return keyword;
    }

    public void setKeyword(String keyword) {
        this.keyword = keyword;
    }
}

package com.xwj.mes.common.api;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;

/**
 * 分页入参基类。pageSize 上限 200，防止脚本误传超大值把单机 MySQL 打满。
 */
public class PageQuery {

    @Min(value = 1, message = "pageNum 最小为 1")
    private long pageNum = 1;

    @Min(value = 1, message = "pageSize 最小为 1")
    @Max(value = 200, message = "pageSize 最大为 200")
    private long pageSize = 10;

    public long getPageNum() {
        return pageNum;
    }

    public void setPageNum(long pageNum) {
        this.pageNum = pageNum;
    }

    public long getPageSize() {
        return pageSize;
    }

    public void setPageSize(long pageSize) {
        this.pageSize = pageSize;
    }
}

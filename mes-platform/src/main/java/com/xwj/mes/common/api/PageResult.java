package com.xwj.mes.common.api;

import java.util.List;

/**
 * 分页结果包装。字段名与 MyBatis-Plus IPage 解耦，避免持久层对象泄漏到接口契约。
 */
public class PageResult<T> {

    private long total;
    private long pageNum;
    private long pageSize;
    private long pages;
    private List<T> records;

    public PageResult() {
    }

    public PageResult(long total, long pageNum, long pageSize, long pages, List<T> records) {
        this.total = total;
        this.pageNum = pageNum;
        this.pageSize = pageSize;
        this.pages = pages;
        this.records = records;
    }

    public static <T> PageResult<T> of(long total, long pageNum, long pageSize, List<T> records) {
        long pages = pageSize <= 0 ? 0 : (total + pageSize - 1) / pageSize;
        return new PageResult<>(total, pageNum, pageSize, pages, records);
    }

    public long getTotal() {
        return total;
    }

    public void setTotal(long total) {
        this.total = total;
    }

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

    public long getPages() {
        return pages;
    }

    public void setPages(long pages) {
        this.pages = pages;
    }

    public List<T> getRecords() {
        return records;
    }

    public void setRecords(List<T> records) {
        this.records = records;
    }
}

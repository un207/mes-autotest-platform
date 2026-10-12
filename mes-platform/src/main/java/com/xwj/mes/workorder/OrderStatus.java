package com.xwj.mes.workorder;

/**
 * 工单状态机。
 *
 * <pre>
 * NEW ──派工──▶ DISPATCHED ──首次报工──▶ IN_PROGRESS ──关闭──▶ CLOSED
 *                    │                        │
 *                    └────────关闭───────────┘
 * </pre>
 *
 * 非法流转一律由 Service 抛 {@code STATE_CONFLICT}，这是接口用例的重点覆盖对象。
 */
public enum OrderStatus {

    /** 新建：仅登记产品与计划数量 */
    NEW("新建"),

    /** 已派工：已指定产线/车间，可开始报工 */
    DISPATCHED("已派工"),

    /** 生产中：已有报工记录 */
    IN_PROGRESS("生产中"),

    /** 已关闭：工单终态，不再接受报工 */
    CLOSED("已关闭");

    private final String label;

    OrderStatus(String label) {
        this.label = label;
    }

    public String getLabel() {
        return label;
    }

    /** 是否处于可报工状态。 */
    public boolean reportable() {
        return this == DISPATCHED || this == IN_PROGRESS;
    }
}

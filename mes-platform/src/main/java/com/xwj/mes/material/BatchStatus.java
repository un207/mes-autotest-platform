package com.xwj.mes.material;

/**
 * 物料批次状态。
 */
public enum BatchStatus {

    /** 在库，未被工单领用 */
    IN_STOCK("在库"),

    /** 在用，已绑定工单 */
    IN_USE("在用"),

    /** 已消耗，投产完成 */
    CONSUMED("已消耗"),

    /** 冻结，质检不合格或待判定，不可投产 */
    FROZEN("冻结");

    private final String label;

    BatchStatus(String label) {
        this.label = label;
    }

    public String getLabel() {
        return label;
    }
}

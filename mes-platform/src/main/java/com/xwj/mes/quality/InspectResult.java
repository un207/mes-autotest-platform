package com.xwj.mes.quality;

/**
 * 质检结论。
 */
public enum InspectResult {

    PASS("合格"),
    FAIL("不合格");

    private final String label;

    InspectResult(String label) {
        this.label = label;
    }

    public String getLabel() {
        return label;
    }

    /**
     * 由数量推导结论：不良数大于 0 即判不合格。
     * 结论不允许人工与数量背离，避免出现「不良 3 个但结论合格」这类不可追溯的数据。
     */
    public static InspectResult derive(int defectiveQty) {
        return defectiveQty > 0 ? FAIL : PASS;
    }
}

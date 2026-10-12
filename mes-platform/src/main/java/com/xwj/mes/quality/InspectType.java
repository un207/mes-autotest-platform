package com.xwj.mes.quality;

/**
 * 质检环节类型（按制造业通行的四段质检划分）。
 */
public enum InspectType {

    /** 来料检验 */
    IQC("来料检验"),

    /** 过程检验 */
    IPQC("过程检验"),

    /** 完工检验 */
    FQC("完工检验"),

    /** 出货检验 */
    OQC("出货检验");

    private final String label;

    InspectType(String label) {
        this.label = label;
    }

    public String getLabel() {
        return label;
    }
}

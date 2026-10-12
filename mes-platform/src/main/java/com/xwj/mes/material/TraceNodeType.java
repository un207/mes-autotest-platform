package com.xwj.mes.material;

/**
 * 追溯节点类型。构成一条完整的产品溯源链：来料 → 投产 → 检验 → 出货。
 */
public enum TraceNodeType {

    /** 来料入库 */
    INBOUND("来料入库"),

    /** 投产（报工） */
    PRODUCE("投产报工"),

    /** 质量检验 */
    INSPECT("质量检验"),

    /** 出货/消耗 */
    OUTBOUND("出货消耗");

    private final String label;

    TraceNodeType(String label) {
        this.label = label;
    }

    public String getLabel() {
        return label;
    }
}

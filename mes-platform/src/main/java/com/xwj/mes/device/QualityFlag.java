package com.xwj.mes.device;

/**
 * 数据质量标记。MES 现场最怕「脏数据静默入账」，因此数采入口必须给出可信度判定。
 */
public enum QualityFlag {

    /** 正常 */
    OK("正常"),

    /** 可疑：数值可解析但超出合理工况区间（如温度 500℃） */
    SUSPECT("可疑"),

    /** 异常：无法解析或字段缺失，数值不入账 */
    BAD("异常");

    private final String label;

    QualityFlag(String label) {
        this.label = label;
    }

    public String getLabel() {
        return label;
    }
}

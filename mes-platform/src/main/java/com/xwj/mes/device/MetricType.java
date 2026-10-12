package com.xwj.mes.device;

/**
 * 设备上报的指标类型。与 M4 阶段 pymodbus 模拟器的寄存器定义一一对应。
 */
public enum MetricType {

    /** 产量计数 */
    OUTPUT("产量"),

    /** 运行状态（0 停机 / 1 运行 / 2 故障） */
    STATUS("运行状态"),

    /** 温度（℃，反映设备工况） */
    TEMPERATURE("温度");

    private final String label;

    MetricType(String label) {
        this.label = label;
    }

    public String getLabel() {
        return label;
    }
}

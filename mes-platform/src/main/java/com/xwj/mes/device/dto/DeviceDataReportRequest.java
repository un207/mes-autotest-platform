package com.xwj.mes.device.dto;

import com.fasterxml.jackson.annotation.JsonFormat;
import com.xwj.mes.device.MetricType;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

import java.time.LocalDateTime;

/**
 * 设备上报入参。
 *
 * <p>{@code rawValue} 刻意声明为 String：现场设备上报畸形数据（空串、乱码、超长）是常态，
 * 入口不做类型强转，交由 Service 判定质量等级后落库。</p>
 */
public record DeviceDataReportRequest(

        @NotBlank(message = "设备编号不能为空")
        @Size(max = 32, message = "设备编号长度不能超过 32")
        String equipmentCode,

        @Size(max = 32, message = "产线编号长度不能超过 32")
        String lineCode,

        @NotNull(message = "指标类型不能为空")
        MetricType metric,

        @NotBlank(message = "上报值不能为空")
        @Size(max = 64, message = "上报值长度不能超过 64")
        String rawValue,

        @Size(max = 16, message = "单位长度不能超过 16")
        String unit,

        @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
        LocalDateTime collectTime
) {
}

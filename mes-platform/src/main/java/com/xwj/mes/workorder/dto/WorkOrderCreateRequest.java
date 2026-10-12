package com.xwj.mes.workorder.dto;

import com.fasterxml.jackson.annotation.JsonFormat;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

import java.time.LocalDateTime;

/**
 * 创建工单入参。
 */
public record WorkOrderCreateRequest(

        @NotBlank(message = "产品编码不能为空")
        @Size(max = 32, message = "产品编码长度不能超过 32")
        String productCode,

        @NotBlank(message = "产品名称不能为空")
        @Size(max = 64, message = "产品名称长度不能超过 64")
        String productName,

        @NotNull(message = "计划数量不能为空")
        @Min(value = 1, message = "计划数量必须大于 0")
        @Max(value = 1000000, message = "计划数量不能超过 1000000")
        Integer planQty,

        @Size(max = 32, message = "产线编号长度不能超过 32")
        String lineCode,

        @Size(max = 64, message = "车间名称长度不能超过 64")
        String workshop,

        @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
        LocalDateTime planStartTime,

        @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
        LocalDateTime planEndTime,

        @Size(max = 255, message = "备注长度不能超过 255")
        String remark
) {
}

package com.xwj.mes.workorder.dto;

import com.fasterxml.jackson.annotation.JsonFormat;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

import java.time.LocalDateTime;

/**
 * 报工入参。
 *
 * <p>{@code qualifiedQty} 与 {@code defectiveQty} 未传时按「全合格」处理；两者都传时必须与
 * {@code reportQty} 相等，由 Service 校验，避免出现「报 100 个、合格 60 个」这类无法追溯的脏数据。</p>
 */
public record WorkReportCreateRequest(

        @NotNull(message = "报工数量不能为空")
        @Min(value = 1, message = "报工数量必须大于 0")
        @Max(value = 1000000, message = "报工数量不能超过 1000000")
        Integer reportQty,

        @Min(value = 0, message = "合格数量不能为负数")
        Integer qualifiedQty,

        @Min(value = 0, message = "不良数量不能为负数")
        Integer defectiveQty,

        @NotBlank(message = "报工人不能为空")
        @Size(max = 32, message = "报工人长度不能超过 32")
        String worker,

        @Size(max = 32, message = "设备编号长度不能超过 32")
        String equipmentCode,

        @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
        LocalDateTime reportTime,

        @Size(max = 255, message = "备注长度不能超过 255")
        String remark
) {
}

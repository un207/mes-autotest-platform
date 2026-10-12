package com.xwj.mes.quality.dto;

import com.fasterxml.jackson.annotation.JsonFormat;
import com.xwj.mes.quality.InspectResult;
import com.xwj.mes.quality.InspectType;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

import java.time.LocalDateTime;

/**
 * 质检录入入参。
 */
public record QualityInspectionCreateRequest(

        @NotBlank(message = "工单号不能为空")
        @Size(max = 32, message = "工单号长度不能超过 32")
        String orderNo,

        @Size(max = 32, message = "批次号长度不能超过 32")
        String batchNo,

        @NotNull(message = "质检类型不能为空")
        InspectType inspectType,

        @NotNull(message = "检验数量不能为空")
        @Min(value = 1, message = "检验数量必须大于 0")
        @Max(value = 1000000, message = "检验数量不能超过 1000000")
        Integer inspectQty,

        @Min(value = 0, message = "合格数量不能为负数")
        Integer qualifiedQty,

        @Min(value = 0, message = "不良数量不能为负数")
        Integer defectiveQty,

        @Size(max = 32, message = "不良代码长度不能超过 32")
        String defectCode,

        /** 可选。传入时必须与数量推导结果一致。 */
        InspectResult result,

        @NotBlank(message = "质检员不能为空")
        @Size(max = 32, message = "质检员长度不能超过 32")
        String inspector,

        @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
        LocalDateTime inspectTime,

        @Size(max = 255, message = "备注长度不能超过 255")
        String remark
) {
}

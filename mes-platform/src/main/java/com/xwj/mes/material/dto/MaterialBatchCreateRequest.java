package com.xwj.mes.material.dto;

import com.fasterxml.jackson.annotation.JsonFormat;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

import java.time.LocalDateTime;

/**
 * 物料批次创建入参。批次号可留空，由系统生成。
 */
public record MaterialBatchCreateRequest(

        @Size(max = 32, message = "批次号长度不能超过 32")
        String batchNo,

        @NotBlank(message = "物料编码不能为空")
        @Size(max = 32, message = "物料编码长度不能超过 32")
        String materialCode,

        @NotBlank(message = "物料名称不能为空")
        @Size(max = 64, message = "物料名称长度不能超过 64")
        String materialName,

        /** 可选，创建时即可绑定工单 */
        @Size(max = 32, message = "工单号长度不能超过 32")
        String orderNo,

        @Size(max = 64, message = "供应商长度不能超过 64")
        String supplier,

        @NotNull(message = "数量不能为空")
        @Min(value = 1, message = "数量必须大于 0")
        Integer qty,

        @Size(max = 16, message = "单位长度不能超过 16")
        String unit,

        @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
        LocalDateTime inboundTime,

        @Size(max = 255, message = "备注长度不能超过 255")
        String remark
) {
}

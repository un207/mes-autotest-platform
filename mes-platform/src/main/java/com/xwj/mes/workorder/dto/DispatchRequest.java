package com.xwj.mes.workorder.dto;

import com.fasterxml.jackson.annotation.JsonFormat;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

import java.time.LocalDateTime;

/**
 * 派工入参。派工后工单进入 DISPATCHED，方可报工。
 */
public record DispatchRequest(

        @NotBlank(message = "产线编号不能为空")
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

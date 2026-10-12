package com.xwj.mes.workorder.dto;

import jakarta.validation.constraints.Size;

/**
 * 关闭工单入参。备注可选。
 */
public record CloseOrderRequest(

        @Size(max = 255, message = "备注长度不能超过 255")
        String remark
) {
}

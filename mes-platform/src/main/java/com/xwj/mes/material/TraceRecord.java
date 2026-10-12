package com.xwj.mes.material;

import com.baomidou.mybatisplus.annotation.TableName;
import com.fasterxml.jackson.annotation.JsonFormat;
import com.xwj.mes.common.entity.BaseEntity;
import lombok.Getter;
import lombok.Setter;

import java.time.LocalDateTime;

/**
 * 追溯记录。不可变流水，只增不改，是「结果可追溯」的落点。
 */
@Getter
@Setter
@TableName("mes_trace_record")
public class TraceRecord extends BaseEntity {

    private static final long serialVersionUID = 1L;

    private String traceNo;

    private String batchNo;

    private String orderNo;

    private TraceNodeType nodeType;

    /** 节点描述，写清发生了什么（如「IPQC：不合格（合格 8 / 不良 2）」） */
    private String nodeDesc;

    private String operator;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime traceTime;
}

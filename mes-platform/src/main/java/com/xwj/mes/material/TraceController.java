package com.xwj.mes.material;

import com.xwj.mes.common.api.ApiResponse;
import com.xwj.mes.material.dto.BatchTraceVO;
import com.xwj.mes.material.dto.OrderTraceVO;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@Tag(name = "追溯", description = "正向（批次→工单）/ 反向（工单→批次）追溯")
@RestController
@RequestMapping("/api/traces")
public class TraceController {

    private final TraceRecordService traceRecordService;

    public TraceController(TraceRecordService traceRecordService) {
        this.traceRecordService = traceRecordService;
    }

    @Operation(summary = "正向追溯：按批次查流向与全链路节点")
    @GetMapping("/batch/{batchNo}")
    public ApiResponse<BatchTraceVO> traceBatch(@PathVariable String batchNo) {
        return ApiResponse.ok(traceRecordService.traceBatch(batchNo));
    }

    @Operation(summary = "反向追溯：按工单查所用批次、节点流水与不良明细")
    @GetMapping("/order/{orderNo}")
    public ApiResponse<OrderTraceVO> traceOrder(@PathVariable String orderNo) {
        return ApiResponse.ok(traceRecordService.traceOrder(orderNo));
    }
}

package com.xwj.mes.workorder;

import com.xwj.mes.common.api.ApiResponse;
import com.xwj.mes.common.api.PageResult;
import com.xwj.mes.workorder.dto.CloseOrderRequest;
import com.xwj.mes.workorder.dto.DispatchRequest;
import com.xwj.mes.workorder.dto.WorkOrderCreateRequest;
import com.xwj.mes.workorder.dto.WorkOrderQuery;
import com.xwj.mes.workorder.dto.WorkOrderVO;
import com.xwj.mes.workorder.dto.WorkReportCreateRequest;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@Tag(name = "工单管理", description = "工单创建 / 派工 / 报工 / 关闭")
@RestController
@RequestMapping("/api/work-orders")
@Validated
public class WorkOrderController {

    private final WorkOrderService workOrderService;

    public WorkOrderController(WorkOrderService workOrderService) {
        this.workOrderService = workOrderService;
    }

    @Operation(summary = "创建工单")
    @PostMapping
    public ApiResponse<WorkOrderVO> create(@Valid @RequestBody WorkOrderCreateRequest req) {
        return ApiResponse.ok(workOrderService.create(req));
    }

    @Operation(summary = "分页查询工单")
    @GetMapping
    public ApiResponse<PageResult<WorkOrderVO>> page(@Valid WorkOrderQuery query) {
        return ApiResponse.ok(workOrderService.page(query));
    }

    @Operation(summary = "查询工单详情（含报工明细）")
    @GetMapping("/{orderNo}")
    public ApiResponse<WorkOrderVO> detail(@PathVariable String orderNo) {
        return ApiResponse.ok(workOrderService.detail(orderNo));
    }

    @Operation(summary = "查询工单报工记录")
    @GetMapping("/{orderNo}/reports")
    public ApiResponse<List<WorkReport>> reports(@PathVariable String orderNo) {
        return ApiResponse.ok(workOrderService.reports(orderNo));
    }

    @Operation(summary = "工单派工")
    @PutMapping("/{orderNo}/dispatch")
    public ApiResponse<WorkOrderVO> dispatch(@PathVariable String orderNo,
                                             @Valid @RequestBody DispatchRequest req) {
        return ApiResponse.ok(workOrderService.dispatch(orderNo, req));
    }

    @Operation(summary = "工单报工")
    @PostMapping("/{orderNo}/reports")
    public ApiResponse<WorkOrderVO> report(@PathVariable String orderNo,
                                           @Valid @RequestBody WorkReportCreateRequest req) {
        return ApiResponse.ok(workOrderService.report(orderNo, req));
    }

    @Operation(summary = "关闭工单")
    @PutMapping("/{orderNo}/close")
    public ApiResponse<WorkOrderVO> close(@PathVariable String orderNo,
                                          @Valid @RequestBody(required = false) CloseOrderRequest req) {
        return ApiResponse.ok(workOrderService.close(orderNo, req));
    }
}

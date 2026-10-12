package com.xwj.mes.material;

import com.xwj.mes.common.api.ApiResponse;
import com.xwj.mes.common.api.PageResult;
import com.xwj.mes.material.dto.MaterialBatchCreateRequest;
import com.xwj.mes.material.dto.MaterialBatchQuery;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@Tag(name = "物料与批次", description = "批次建档 / 绑定工单 / 出货消耗")
@RestController
@RequestMapping("/api/material-batches")
@Validated
public class MaterialBatchController {

    private final MaterialBatchService materialBatchService;

    public MaterialBatchController(MaterialBatchService materialBatchService) {
        this.materialBatchService = materialBatchService;
    }

    @Operation(summary = "创建物料批次")
    @PostMapping
    public ApiResponse<MaterialBatch> create(@Valid @RequestBody MaterialBatchCreateRequest req) {
        return ApiResponse.ok(materialBatchService.create(req));
    }

    @Operation(summary = "分页查询批次")
    @GetMapping
    public ApiResponse<PageResult<MaterialBatch>> page(@Valid MaterialBatchQuery query) {
        return ApiResponse.ok(materialBatchService.page(query));
    }

    @Operation(summary = "按工单查询批次")
    @GetMapping("/by-order/{orderNo}")
    public ApiResponse<List<MaterialBatch>> byOrder(@PathVariable String orderNo) {
        return ApiResponse.ok(materialBatchService.byOrder(orderNo));
    }

    @Operation(summary = "查询批次详情")
    @GetMapping("/{batchNo}")
    public ApiResponse<MaterialBatch> detail(@PathVariable String batchNo) {
        return ApiResponse.ok(materialBatchService.detail(batchNo));
    }

    @Operation(summary = "批次绑定工单")
    @PutMapping("/{batchNo}/bind")
    public ApiResponse<MaterialBatch> bind(@PathVariable String batchNo,
                                          @RequestParam @NotBlank(message = "工单号不能为空") String orderNo) {
        return ApiResponse.ok(materialBatchService.bind(batchNo, orderNo));
    }

    @Operation(summary = "批次出货消耗")
    @PutMapping("/{batchNo}/outbound")
    public ApiResponse<MaterialBatch> outbound(@PathVariable String batchNo,
                                               @RequestParam(required = false) String operator) {
        return ApiResponse.ok(materialBatchService.outbound(batchNo, operator));
    }
}

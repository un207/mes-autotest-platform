package com.xwj.mes.quality;

import com.xwj.mes.common.api.ApiResponse;
import com.xwj.mes.common.api.PageResult;
import com.xwj.mes.quality.dto.QualityInspectionCreateRequest;
import com.xwj.mes.quality.dto.QualityInspectionQuery;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Map;

@Tag(name = "质量管理", description = "质检录入 / 查询 / 不良追溯")
@RestController
@RequestMapping("/api/quality-inspections")
@Validated
public class QualityInspectionController {

    private final QualityInspectionService qualityInspectionService;

    public QualityInspectionController(QualityInspectionService qualityInspectionService) {
        this.qualityInspectionService = qualityInspectionService;
    }

    @Operation(summary = "录入质检记录")
    @PostMapping
    public ApiResponse<QualityInspection> create(@Valid @RequestBody QualityInspectionCreateRequest req) {
        return ApiResponse.ok(qualityInspectionService.create(req));
    }

    @Operation(summary = "分页查询质检记录")
    @GetMapping
    public ApiResponse<PageResult<QualityInspection>> page(@Valid QualityInspectionQuery query) {
        return ApiResponse.ok(qualityInspectionService.page(query));
    }

    @Operation(summary = "不良代码分布统计")
    @GetMapping("/defect-summary")
    public ApiResponse<List<Map<String, Object>>> defectSummary() {
        return ApiResponse.ok(qualityInspectionService.defectSummary());
    }

    @Operation(summary = "按工单追溯不良明细")
    @GetMapping("/defects/{orderNo}")
    public ApiResponse<List<QualityInspection>> defects(@PathVariable String orderNo) {
        return ApiResponse.ok(qualityInspectionService.defectsByOrder(orderNo));
    }

    @Operation(summary = "查询质检单详情")
    @GetMapping("/{inspectNo}")
    public ApiResponse<QualityInspection> detail(@PathVariable String inspectNo) {
        return ApiResponse.ok(qualityInspectionService.detail(inspectNo));
    }
}

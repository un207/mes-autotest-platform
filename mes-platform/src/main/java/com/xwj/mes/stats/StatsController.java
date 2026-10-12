package com.xwj.mes.stats;

import com.xwj.mes.common.api.ApiResponse;
import com.xwj.mes.stats.dto.OrderYieldVO;
import com.xwj.mes.stats.dto.OverviewVO;
import com.xwj.mes.stats.dto.ProductionStatVO;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.time.LocalDate;
import java.util.List;

@Tag(name = "统计报表", description = "产量日报 / 良率 / 平台总览")
@RestController
@RequestMapping("/api/stats")
@Validated
public class StatsController {

    private final StatsService statsService;

    public StatsController(StatsService statsService) {
        this.statsService = statsService;
    }

    @Operation(summary = "平台总览指标")
    @GetMapping("/overview")
    public ApiResponse<OverviewVO> overview() {
        return ApiResponse.ok(statsService.overview());
    }

    @Operation(summary = "产量日报（按日期 × 产线）")
    @GetMapping("/production")
    public ApiResponse<List<ProductionStatVO>> production(
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate from,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate to,
            @RequestParam(required = false) String lineCode) {
        return ApiResponse.ok(statsService.dailyProduction(from, to, lineCode));
    }

    @Operation(summary = "低良率工单排行")
    @GetMapping("/yield/orders")
    public ApiResponse<List<OrderYieldVO>> lowYieldOrders(
            @RequestParam(defaultValue = "10") @Min(1) @Max(100) int limit) {
        return ApiResponse.ok(statsService.lowYieldOrders(limit));
    }
}

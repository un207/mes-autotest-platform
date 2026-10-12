package com.xwj.mes.device;

import com.xwj.mes.common.api.ApiResponse;
import com.xwj.mes.common.api.PageResult;
import com.xwj.mes.device.dto.DeviceDataQuery;
import com.xwj.mes.device.dto.DeviceDataReportRequest;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@Tag(name = "设备数采", description = "接收设备/模拟器上报数据，含脏数据质量判定")
@RestController
@RequestMapping("/api/device-data")
@Validated
public class DeviceDataController {

    private final DeviceDataService deviceDataService;

    public DeviceDataController(DeviceDataService deviceDataService) {
        this.deviceDataService = deviceDataService;
    }

    @Operation(summary = "单条数据上报")
    @PostMapping
    public ApiResponse<DeviceData> report(@Valid @RequestBody DeviceDataReportRequest req) {
        return ApiResponse.ok(deviceDataService.ingest(req));
    }

    @Operation(summary = "批量数据上报（单次上限 200 条）")
    @PostMapping("/batch")
    public ApiResponse<List<DeviceData>> reportBatch(@Valid @RequestBody List<DeviceDataReportRequest> reqs) {
        return ApiResponse.ok(deviceDataService.ingestBatch(reqs));
    }

    @Operation(summary = "分页查询数采记录")
    @GetMapping
    public ApiResponse<PageResult<DeviceData>> page(@Valid DeviceDataQuery query) {
        return ApiResponse.ok(deviceDataService.page(query));
    }

    @Operation(summary = "查询异常/可疑数采记录")
    @GetMapping("/abnormal")
    public ApiResponse<List<DeviceData>> abnormal(
            @RequestParam(defaultValue = "20") @Min(1) @Max(200) int limit) {
        return ApiResponse.ok(deviceDataService.abnormal(limit));
    }
}

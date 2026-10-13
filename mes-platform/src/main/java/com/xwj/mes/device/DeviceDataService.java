package com.xwj.mes.device;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.xwj.mes.common.api.ErrorCode;
import com.xwj.mes.common.api.PageResult;
import com.xwj.mes.common.exception.BizException;
import com.xwj.mes.common.util.TextUtils;
import com.xwj.mes.device.dto.DeviceDataQuery;
import com.xwj.mes.device.dto.DeviceDataReportRequest;
import com.xwj.mes.device.mapper.DeviceDataMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * 设备数采服务。
 *
 * <p>数采入口是「脏数据」进入 MES 的唯一通道，因此这里做三层把关：
 * 可解析性（非数值直接判 BAD，数值不入账）→ 工况区间（超限判 SUSPECT 但仍留档）→
 * 时间合理性（未来时间判 SUSPECT）。异常数据一律留痕，不做静默丢弃。</p>
 */
@Service
public class DeviceDataService {

    private static final Logger log = LoggerFactory.getLogger(DeviceDataService.class);

    /** 单次批量上报上限，防止模拟器异常刷爆单机 MySQL */
    private static final int MAX_BATCH_SIZE = 200;

    /** 允许的采集时间偏移上限（分钟）：超过当前时间 5 分钟视为设备时钟异常 */
    private static final long FUTURE_TOLERANCE_MINUTES = 5;

    /** 各指标的合理工况区间 */
    private static final Map<MetricType, BigDecimal[]> RANGES = Map.of(
            MetricType.OUTPUT, new BigDecimal[]{BigDecimal.ZERO, new BigDecimal("1000000")},
            MetricType.STATUS, new BigDecimal[]{BigDecimal.ZERO, new BigDecimal("10")},
            MetricType.TEMPERATURE, new BigDecimal[]{new BigDecimal("-50"), new BigDecimal("200")}
    );

    private final DeviceDataMapper deviceDataMapper;

    public DeviceDataService(DeviceDataMapper deviceDataMapper) {
        this.deviceDataMapper = deviceDataMapper;
    }

    @Transactional(rollbackFor = Exception.class)
    public DeviceData ingest(DeviceDataReportRequest req) {
        DeviceData data = build(req);
        deviceDataMapper.insert(data);
        if (data.getQualityFlag() != QualityFlag.OK) {
            log.warn("数采异常入账 equipment={} metric={} raw={} flag={} reason={}",
                    data.getEquipmentCode(), data.getMetric(), data.getRawValue(),
                    data.getQualityFlag(), data.getQualityMessage());
        }
        return data;
    }

    @Transactional(rollbackFor = Exception.class)
    public List<DeviceData> ingestBatch(List<DeviceDataReportRequest> requests) {
        if (requests == null || requests.isEmpty()) {
            throw new BizException(ErrorCode.PARAM_INVALID, "批量上报列表不能为空");
        }
        if (requests.size() > MAX_BATCH_SIZE) {
            throw new BizException(ErrorCode.PARAM_INVALID,
                    "单次批量上报不能超过 " + MAX_BATCH_SIZE + " 条，当前 " + requests.size() + " 条");
        }
        List<DeviceData> saved = new ArrayList<>(requests.size());
        int abnormal = 0;
        for (DeviceDataReportRequest req : requests) {
            DeviceData data = build(req);
            deviceDataMapper.insert(data);
            if (data.getQualityFlag() != QualityFlag.OK) {
                abnormal++;
            }
            saved.add(data);
        }
        log.info("批量数采入库 {} 条，其中异常/可疑 {} 条", saved.size(), abnormal);
        return saved;
    }

    public PageResult<DeviceData> page(DeviceDataQuery query) {
        LambdaQueryWrapper<DeviceData> wrapper = new LambdaQueryWrapper<DeviceData>()
                .eq(StringUtils.hasText(query.getEquipmentCode()), DeviceData::getEquipmentCode, query.getEquipmentCode())
                .eq(StringUtils.hasText(query.getLineCode()), DeviceData::getLineCode, query.getLineCode())
                .eq(query.getMetric() != null, DeviceData::getMetric, query.getMetric())
                .eq(query.getQualityFlag() != null, DeviceData::getQualityFlag, query.getQualityFlag())
                // 同一轮上报的多个指标共用同一个采集时间（秒级精度），仅按时间排序时同刻记录的顺序
                // 取决于插入先后，而插入是并发的，会导致列表顺序在刷新间跳变。补一个 metric 作为
                // 次级排序键，使同一时刻的记录稳定呈现为 产量 → 运行状态 → 温度（枚举名字典序正好如此）。
                .orderByDesc(DeviceData::getCollectTime)
                .orderByAsc(DeviceData::getMetric)
                .orderByDesc(DeviceData::getId);

        Page<DeviceData> page = deviceDataMapper.selectPage(
                new Page<>(query.getPageNum(), query.getPageSize()), wrapper);
        return PageResult.of(page.getTotal(), page.getCurrent(), page.getSize(), page.getRecords());
    }

    /** 异常/可疑数据列表，供现场排查与用例断言。 */
    public List<DeviceData> abnormal(int limit) {
        int safeLimit = Math.min(Math.max(limit, 1), 200);
        return deviceDataMapper.selectAbnormal(safeLimit);
    }

    private DeviceData build(DeviceDataReportRequest req) {
        DeviceData data = new DeviceData();
        data.setEquipmentCode(req.equipmentCode().trim());
        data.setLineCode(TextUtils.nullIfBlank(req.lineCode()));
        data.setMetric(req.metric());
        data.setRawValue(req.rawValue().trim());
        data.setUnit(TextUtils.nullIfBlank(req.unit()));

        LocalDateTime collectTime = req.collectTime() == null ? LocalDateTime.now() : req.collectTime();
        data.setCollectTime(collectTime);

        // 第一层：可解析性
        BigDecimal value;
        try {
            value = new BigDecimal(req.rawValue().trim());
        } catch (NumberFormatException e) {
            data.setMetricValue(null);
            data.setQualityFlag(QualityFlag.BAD);
            data.setQualityMessage("上报值无法解析为数值，已标记异常且不入账");
            return data;
        }
        data.setMetricValue(value);

        // 第二层：工况区间
        BigDecimal[] range = RANGES.get(req.metric());
        if (range != null && (value.compareTo(range[0]) < 0 || value.compareTo(range[1]) > 0)) {
            data.setQualityFlag(QualityFlag.SUSPECT);
            data.setQualityMessage("数值超出合理区间 [" + range[0].toPlainString() + ", "
                    + range[1].toPlainString() + "]");
            return data;
        }

        // 第三层：时间合理性
        if (collectTime.isAfter(LocalDateTime.now().plusMinutes(FUTURE_TOLERANCE_MINUTES))) {
            data.setQualityFlag(QualityFlag.SUSPECT);
            data.setQualityMessage("采集时间晚于当前时间超过 " + FUTURE_TOLERANCE_MINUTES + " 分钟，疑为设备时钟异常");
            return data;
        }

        data.setQualityFlag(QualityFlag.OK);
        data.setQualityMessage(null);
        return data;
    }
}

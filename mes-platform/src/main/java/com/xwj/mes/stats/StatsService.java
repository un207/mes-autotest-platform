package com.xwj.mes.stats;

import com.xwj.mes.common.api.ErrorCode;
import com.xwj.mes.common.exception.BizException;
import com.xwj.mes.stats.dto.OrderYieldVO;
import com.xwj.mes.stats.dto.OverviewVO;
import com.xwj.mes.stats.dto.ProductionStatVO;
import com.xwj.mes.stats.mapper.StatsMapper;
import org.springframework.stereotype.Service;

import java.time.LocalDate;
import java.util.List;

/**
 * 统计服务。入参日期为闭开区间 [from, to+1)。
 */
@Service
public class StatsService {

    /** 单次查询的最大跨度，避免脚本传个宽区间把库扫穿 */
    private static final int MAX_RANGE_DAYS = 92;

    private final StatsMapper statsMapper;

    public StatsService(StatsMapper statsMapper) {
        this.statsMapper = statsMapper;
    }

    public List<ProductionStatVO> dailyProduction(LocalDate from, LocalDate to, String lineCode) {
        LocalDate start = from == null ? LocalDate.now().minusDays(6) : from;
        LocalDate end = to == null ? LocalDate.now() : to;

        if (end.isBefore(start)) {
            throw new BizException(ErrorCode.PARAM_INVALID, "结束日期不能早于开始日期");
        }
        if (start.plusDays(MAX_RANGE_DAYS).isBefore(end)) {
            throw new BizException(ErrorCode.PARAM_INVALID, "查询区间不能超过 " + MAX_RANGE_DAYS + " 天");
        }

        return statsMapper.selectDailyProduction(
                start.atStartOfDay(), end.plusDays(1).atStartOfDay(), lineCode);
    }

    public OverviewVO overview() {
        return statsMapper.selectOverview();
    }

    public List<OrderYieldVO> lowYieldOrders(int limit) {
        int safeLimit = Math.min(Math.max(limit, 1), 100);
        return statsMapper.selectLowYieldOrders(safeLimit);
    }
}

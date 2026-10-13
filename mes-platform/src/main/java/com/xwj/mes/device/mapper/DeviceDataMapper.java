package com.xwj.mes.device.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.xwj.mes.device.DeviceData;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

import java.util.List;

@Mapper
public interface DeviceDataMapper extends BaseMapper<DeviceData> {

    /**
     * 异常/可疑数据列表，供现场排查与用例断言。
     *
     * <p>次级排序键用 metric：同一轮上报的多个指标采集时间相同（秒级精度），
     * 只按时间排序时同刻记录的顺序不稳定。加 metric 后固定为 产量 → 运行状态 → 温度。</p>
     */
    @Select("SELECT * FROM mes_device_data WHERE quality_flag <> 'OK' AND deleted = 0 "
            + "ORDER BY collect_time DESC, metric ASC, id DESC LIMIT #{limit}")
    List<DeviceData> selectAbnormal(@Param("limit") int limit);

    @Select("SELECT COUNT(*) FROM mes_device_data WHERE equipment_code = #{equipmentCode} "
            + "AND metric = #{metric} AND deleted = 0")
    long countByEquipmentAndMetric(@Param("equipmentCode") String equipmentCode, @Param("metric") String metric);
}

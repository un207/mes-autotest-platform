package com.xwj.mes.device.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.xwj.mes.device.DeviceData;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

import java.util.List;

@Mapper
public interface DeviceDataMapper extends BaseMapper<DeviceData> {

    @Select("SELECT * FROM mes_device_data WHERE quality_flag <> 'OK' AND deleted = 0 "
            + "ORDER BY collect_time DESC, id DESC LIMIT #{limit}")
    List<DeviceData> selectAbnormal(@Param("limit") int limit);

    @Select("SELECT COUNT(*) FROM mes_device_data WHERE equipment_code = #{equipmentCode} "
            + "AND metric = #{metric} AND deleted = 0")
    long countByEquipmentAndMetric(@Param("equipmentCode") String equipmentCode, @Param("metric") String metric);
}

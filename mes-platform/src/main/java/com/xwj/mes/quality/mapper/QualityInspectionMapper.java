package com.xwj.mes.quality.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.xwj.mes.quality.QualityInspection;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

import java.util.List;
import java.util.Map;

@Mapper
public interface QualityInspectionMapper extends BaseMapper<QualityInspection> {

    /** 不良明细，供追溯接口使用。 */
    @Select("SELECT * FROM mes_quality_inspection "
            + "WHERE order_no = #{orderNo} AND result = 'FAIL' AND deleted = 0 "
            + "ORDER BY inspect_time ASC, id ASC")
    List<QualityInspection> selectDefectsByOrderNo(@Param("orderNo") String orderNo);

    @Select("SELECT * FROM mes_quality_inspection "
            + "WHERE batch_no = #{batchNo} AND deleted = 0 ORDER BY inspect_time ASC, id ASC")
    List<QualityInspection> selectByBatchNo(@Param("batchNo") String batchNo);

    /** 按不良代码汇总，避免应用层遍历统计。 */
    @Select("SELECT defect_code AS defectCode, COUNT(*) AS cnt, IFNULL(SUM(defective_qty), 0) AS defectiveQty "
            + "FROM mes_quality_inspection WHERE deleted = 0 AND result = 'FAIL' AND defect_code IS NOT NULL "
            + "GROUP BY defect_code ORDER BY defectiveQty DESC")
    List<Map<String, Object>> sumDefectsByCode();
}

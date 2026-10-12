package com.xwj.mes.workorder.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.xwj.mes.workorder.WorkReport;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

import java.util.List;
import java.util.Map;

@Mapper
public interface WorkReportMapper extends BaseMapper<WorkReport> {

    @Select("SELECT * FROM mes_work_report WHERE order_no = #{orderNo} AND deleted = 0 ORDER BY report_time ASC, id ASC")
    List<WorkReport> selectByOrderNo(@Param("orderNo") String orderNo);

    /**
     * 按工单汇总报工（合格/不良总数）。
     * 汇总下沉到 SQL，避免把整表报工记录捞进内存再相加。
     */
    @Select("SELECT IFNULL(SUM(report_qty), 0) AS reportQty, "
            + "IFNULL(SUM(qualified_qty), 0) AS qualifiedQty, "
            + "IFNULL(SUM(defective_qty), 0) AS defectiveQty "
            + "FROM mes_work_report WHERE order_no = #{orderNo} AND deleted = 0")
    Map<String, Object> sumByOrderNo(@Param("orderNo") String orderNo);
}
